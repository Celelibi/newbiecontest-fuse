#!/usr/bin/env python
# coding: utf-8

import os
import errno
import time
import re
import fuse
import requests
import lxml.html

import fileobjects as fo

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



class News(object):
    newspath = "/news"
    urlnews = "index.php?page=news"
    newslife = 60
    datere = re.compile('^(\d+ \d+ \d+ à \d+:\d+:\d+)')


    def __init__(self, req):
        self.req = req
        self.newslist = None
        self.newsexpir = None


    def handledpath(self):
        return [self.newspath]


    def _getnews(self):
        now = time.time()
        if self.newslist is not None and self.newsexpir > now:
            return

        res = self.req.get(self.urlnews)
        doc = lxml.html.fromstring(res.content, base_url = res.url)
        elements = doc.cssselect('div#content > div.textpad > *')

        monthdict = {
                "Janvier" : "01", "Février" : "02", "Mars" : "03",
                "Avril" : "04", "Mai" : "05", "Juin" : "06", "Juillet" : "07",
                "Août" : "08", "Septembre" : "09", "Octobre" : "10",
                "Novembre" : "11", "Décembre" : "12"
        }
        self.newslist = {}

        for i in range(0, len(elements), 4):
            # The list end with a single <p>
            if i + 4 > len(elements):
                break

            [title, content, foot, hr] = elements[i:i+4]
            if title.tag != 'h2' or hr.tag != 'hr':
                raise ParsingException()

            # Build a File object
            titletext = title.text
            titletext = titletext.strip().replace('/', '_')
            news = fo.File(titletext)

            # Try to render the html
            try:
                import html2text
                htmlcontent = lxml.html.tostring(content, method = 'html')
                news.content = html2text.html2text(htmlcontent).encode('utf-8')
            except ImportError:
                news.content = lxml.html.tostring(content, encoding = 'utf-8', method = 'text')


            # Parse the publish date of the news and set it as the File's stat
            date = lxml.html.tostring(foot, encoding = 'utf-8', method = 'text')
            for a, n in monthdict.items():
                date = date.replace(a, n)

            match = self.datere.match(date)
            if match is None:
                raise ParsingException()

            date = match.group(1)
            date = time.strptime(date, "%d %m %Y à %H:%M:%S")
            news.stat.st_mtime = time.mktime(date)
            news.stat.st_ctime = news.stat.st_mtime

            # Add the File to the list
            self.newslist[self.newspath + "/" + news.name] = news
        self.newsexpir = now + self.newslife


    def getattr(self, path):
        self._getnews()
        if path == self.newspath:
            return fo.DirStat()
        elif path in self.newslist:
            return self.newslist[path].stat
        else:
            return -errno.ENOENT


    def readdir(self, path, offset):
        self._getnews()

        yield fuse.Direntry(".")
        yield fuse.Direntry("..")
        for f in self.newslist.values():
            yield fuse.Direntry(f.name)


    def open(self, path, flags):
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES

        self._getnews()

        if path not in self.newslist:
            # Should not happen because fuse always call getattr first
            return -errno.ENOENT


    def read(self, path, size, offset):
        self._getnews()
        return self.newslist[path].content[offset:offset+size]



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
    modules = [req, News(req), Challenges(req)]
    server = NewbiecontestFS(modules, usage = usage)
    server.parse(errex = 1)
    server.main()


if __name__ == '__main__':
    main()
