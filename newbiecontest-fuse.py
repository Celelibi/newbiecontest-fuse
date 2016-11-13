#!/usr/bin/env python
# coding: utf-8

import errno
import time
import fuse
import requests
import lxml.html

import fileobjects as fo
import modules.news as news

fuse.fuse_python_api = (0, 2)


class AuthException(BaseException):
    pass


class Challenges(object):
    challpath = "/challenges"
    urlcat = "index.php?page=challenges"
    cachelife = 60


    class Category(object):
        def __init__(self, name, link = None):
            self.name = name
            self.link = link
            self.dir = fo.Directory(name)


    def __init__(self, req):
        self.req = req
        self.catdirs = None
        self.catexpir = None


    def handledpath(self):
        return [self.challpath]


    def _getcategories(self):
        now = time.time()
        if self.catdirs is not None and self.catexpir > now:
            return

        res = self.req.get(self.urlcat)
        doc = lxml.html.fromstring(res.content, base_url = res.url)
        tables = doc.cssselect('div#content > div.textpad > table')

        if len(tables) != 3:
            raise ParsingException()

        self.catdirs = {}

        # Categories are linked in the first table
        tablecat = tables[0]
        for link in tablecat.cssselect('tr strong a'):
            caturl = link.get('href')
            catname = lxml.html.tostring(link, encoding = 'utf-8', method = 'text').strip()

            if not catname.startswith('Épreuves '):
                continue

            catname = catname[len('Épreuves '):]
            self.catdirs[self.challpath + "/" + catname] = self.Category(catname, caturl)

        self.catexpir = now + self.cachelife


    def getattr(self, path):
        self._getcategories()

        if path == self.challpath:
            st = fo.DirStat()
            st.st_nlink += len(self.catdirs)
            return st
        elif path in self.catdirs:
            return self.catdirs[path].dir.stat
        else:
            return -errno.ENOENT


    def readdir(self, path, offset):
        self._getcategories()

        yield fuse.Direntry(".")
        yield fuse.Direntry("..")
        for f in self.catdirs.values():
            yield fuse.Direntry(f.name)



class Requests(object):
    """Make all the requests through and manage the authentication and cookies.

    This class is responsible for the virtual files /username and /password."""

    urlbase = "https://www.newbiecontest.org/"
    urlauth = "forums/index.php?action=login2"

    def __init__(self):
        self.username = ''
        self.password = ''
        self.cookies = None
        self.files = {}

        uf = fo.File("username", isWritable = True)
        pf = fo.File("password", isWritable = True, content = b"<password is write-only>\n")
        df = fo.File("deauth", isWritable = True, content = b"Write 1 to this file to logout\n")

        for f in [uf, pf, df]:
            path = "/" + f.name
            self.files[path] = f


    def handledpath(self):
        return self.files.keys()


    def get(self, url, **kwargs):
        resp = requests.get(self.urlbase + url, cookies = self.cookies, **kwargs)
        self.cookies = resp.cookies
        return resp


    def post(self, url, **kwargs):
        resp = requests.post(self.urlbase + url, cookies = self.cookies, **kwargs)
        self.cookies = resp.cookies
        return resp


    def auth(self):
        self.deauth()
        cred = {'user' : self.username, 'passwrd' : self.password}
        resp = self.post(self.urlauth, data = cred)

        if resp.url.endswith(self.urlauth):
            raise AuthException

        self.cookies = resp.history[0].cookies
        return resp


    def deauth(self):
        self.cookies = None


    def getattr(self, path):
        return self.files[path].stat


    def open(self, path, flags):
        pass


    def read(self, path, size, offset):
        return self.files[path].content[offset:offset+size]


    def write(self, path, buf, offset):
        buflen = len(buf)
        buf = buf.rstrip("\r\n")

        if path == "/username":
            self.files[path].content = bytes(buf + "\n")
            if buf != self.username:
                self.deauth()
                self.username = buf
            return buflen

        elif path == "/password":
            if buf != self.username:
                self.deauth()
                self.password = buf
            return buflen

        elif path == "/deauth":
            if int(buf):
                self.deauth()
            return buflen


    def truncate(self, path, length):
        if path == "/username":
            c = self.files[path].content
            c = c[:length] + b"\0" * (length - len(c))
            self.files[path].content = c

            if c.rstrip("\r\n") != self.username:
                self.deauth()
                self.username = c.rstrip("\r\n")

        elif path == "/password":
            c = self.password
            c = c[:length] + b"\0" * (length - len(c))

            if c != self.password:
                self.deauth()
                self.password = c

        elif path == "/deauth":
            pass



class NewbiecontestFS(fuse.Fuse):
    def __init__(self, modules = [], *args, **kwargs):
        super(NewbiecontestFS, self).__init__(*args, **kwargs)
        self.modules = modules
        self.pathmodule = {}

        for m in modules:
            for p in m.handledpath():
                self.pathmodule[p] = m


    @staticmethod
    def pathprefix(path):
        secondslashidx = path.find("/", 1)
        if secondslashidx == -1:
            secondslashidx = len(path)
        return path[:secondslashidx]


    def getattr(self, path):
        prefix = self.pathprefix(path)

        if path == "/":
            return fo.DirStat()
        elif prefix in self.pathmodule:
            return self.pathmodule[prefix].getattr(path)

        return -errno.ENOENT


    def readdir(self, path, offset):
        # Stupid trick because a single function can't both yield and return
        def rootreaddir():
            yield fuse.Direntry(".")
            yield fuse.Direntry("..")
            for name in self.pathmodule.keys():
                yield fuse.Direntry(name[1:])

        prefix = self.pathprefix(path)

        if path == "/":
            return rootreaddir()
        elif prefix in self.pathmodule:
            return self.pathmodule[prefix].readdir(path, offset)
        else:
            return -errno.ENOENT


    def open(self, path, *args, **kwargs):
        prefix = self.pathprefix(path)
        if prefix in self.pathmodule:
            return self.pathmodule[prefix].open(path, *args, **kwargs)

        return -errno.ENOENT


    def read(self, path, *args, **kwargs):
        prefix = self.pathprefix(path)
        if prefix in self.pathmodule:
            return self.pathmodule[prefix].read(path, *args, **kwargs)


    def write(self, path, *args, **kwargs):
        prefix = self.pathprefix(path)
        if prefix in self.pathmodule:
            return self.pathmodule[prefix].write(path, *args, **kwargs)


    def truncate(self, path, *args, **kwargs):
        prefix = self.pathprefix(path)
        if prefix in self.pathmodule:
            return self.pathmodule[prefix].truncate(path, *args, **kwargs)



def main():
    usage = "Newbiecontest File System\n\n"
    usage += NewbiecontestFS.fusage

    req = Requests()
    modules = [req, news.News(req), Challenges(req)]
    server = NewbiecontestFS(modules, usage = usage)
    server.parse(errex = 1)
    server.main()


if __name__ == '__main__':
    main()
