#!/usr/bin/env python
# coding: utf-8

import os
import sys
import errno
import stat
import time
import re
import fuse
import requests
import lxml.html


fuse.fuse_python_api = (0, 2)


class AuthException(BaseException):
    pass

class ParsingException(BaseException):
    pass


class DefaultStat(fuse.Stat):
    def __init__(self, *args, **kwargs):
        super(DefaultStat, self).__init__(*args, **kwargs)
        # These fields are purely cosmetic
        self.st_uid = os.getuid()
        self.st_gid = os.getgid()
        self.st_atime = int(time.time())
        self.st_mtime = self.st_atime
        self.st_ctime = self.st_atime

    def touch(self):
        self.st_atime = int(time.time())
        self.st_mtime = self.st_atime


class DirStat(DefaultStat):
    def __init__(self, *args, **kwargs):
        super(DirStat, self).__init__(*args, **kwargs)
        # Those two fields are require
        self.st_mode = stat.S_IFDIR | 0555
        self.st_nlink = 2


class FileStat(DefaultStat):
    def __init__(self, *args, **kwargs):
        super(FileStat, self).__init__(*args, **kwargs)
        # Those two fields are require
        self.st_mode = stat.S_IFREG | 0444
        self.st_nlink = 1


class File(object):
    def __init__(self, name, isWritable = True, content = b''):
        self.stat = FileStat()
        if isWritable:
            self.stat.st_mode |= 0220
        self.name = name
        self._content = content
        self.stat.st_size = len(content)

    @property
    def content(self):
        self.stat.st_atime = int(time.time())
        return self._content

    @content.setter
    def content(self, content):
        self._content = content
        self.stat.st_size = len(content)
        self.stat.touch()
        return self._content


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
            news = File(titletext, isWritable = False)

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
            return DirStat()
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

        uf = File("username")
        pf = File("password", content = b"<password is write-only>\n")
        df = File("deauth", content = b"Write 1 to this file to logout\n")

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
            return DirStat()
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
    modules = [req, News(req)]
    server = NewbiecontestFS(modules, usage = usage)
    server.parse(errex = 1)
    server.main()


if __name__ == '__main__':
    main()
