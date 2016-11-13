#!/usr/bin/env python
# coding: utf-8

import os
import sys
import errno
import stat
import time
import fuse
import requests


fuse.fuse_python_api = (0, 2)


class AuthException(BaseException):
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


# TODO
# Modules: news, challenges, shoutbox


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


    def getattr(self, path):
        if path == "/":
            return DirStat()
        elif path in self.pathmodule:
            return self.pathmodule[path].getattr(path)

        return -errno.ENOENT


    def readdir(self, path, offset):
        # Stupid trick because a single function can't both yield and return
        def rootreaddir():
            yield fuse.Direntry(".")
            yield fuse.Direntry("..")
            for name in self.pathmodule.keys():
                yield fuse.Direntry(name[1:])

        if path == "/":
            return rootreaddir()
        elif path in self.pathmodule:
            return self.pathmodule[path].readdir(path, offset)
        else:
            return -errno.ENOENT


    def open(self, path, *args, **kwargs):
        if path in self.pathmodule:
            return self.pathmodule[path].open(path, *args, **kwargs)

        return -errno.ENOENT


    def read(self, path, *args, **kwargs):
        if path in self.pathmodule:
            return self.pathmodule[path].read(path, *args, **kwargs)


    def write(self, path, *args, **kwargs):
        if path in self.pathmodule:
            return self.pathmodule[path].write(path, *args, **kwargs)


    def truncate(self, path, *args, **kwargs):
        if path in self.pathmodule:
            return self.pathmodule[path].truncate(path, *args, **kwargs)



def main():
    usage = "Newbiecontest File System\n\n"
    usage += NewbiecontestFS.fusage

    modules = [Requests()]
    server = NewbiecontestFS(modules, usage = usage)
    server.parse(errex = 1)
    server.main()


if __name__ == '__main__':
    main()
