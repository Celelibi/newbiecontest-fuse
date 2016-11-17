#!/usr/bin/env python
# coding: utf-8

import errno
import fuse
import itertools

import fileobjects as fo
import modules.news as news
import modules.challenges as challenges
import modules.authrequests as authrequests

fuse.fuse_python_api = (0, 2)



class NewbiecontestFS(fuse.Fuse):
    def __init__(self, *args, **kwargs):
        super(NewbiecontestFS, self).__init__(*args, **kwargs)

        req = authrequests.AuthRequests()

        self.rootmodule = authrequests.Auth(req)

        self.dirmodules = {}
        self.dirmodules["news"] = news.News(req)
        self.dirmodules["challenges"] = challenges.Challenges(req)


    @staticmethod
    def pathsplit(path):
        idx = path.find("/")
        if idx == -1:
            idx = len(path)
        return (path[:idx], path[idx+1:])


    def modulepath(self, path):
        (prefix, tail) = self.pathsplit(path)
        if prefix in self.dirmodules:
            return (self.dirmodules[prefix], tail)
        return (self.rootmodule, path)


    def getattr(self, path):
        path = path[1:]
        (m, tail) = self.modulepath(path)

        if tail == "":
            # Asking for / or a dirmodule
            st = fo.DirStat()
            st.st_nlink += m.getndirs()

            if path == "":
                st.st_nlink += len(self.dirmodules)
            return st

        else:
            # Asking for a module's content
            return m.getattr(tail)


    def readdir(self, path, offset):
        dotdot = [fuse.Direntry("."), fuse.Direntry("..")]
        path = path[1:]
        (m, tail) = self.modulepath(path)

        if tail == "":
            f = [m.readdir(tail, offset)]
            if path == "":
                f.append(fuse.Direntry(name) for name in self.dirmodules.keys())
            return itertools.chain(dotdot, *f)

        else:
            return m.readdir(tail, offset)


    def open(self, path, *args, **kwargs):
        path = path[1:]
        (m, tail) = self.modulepath(path)

        if tail == "":
            return -errno.EISDIR

        return m.open(tail, *args, **kwargs)


    def read(self, path, *args, **kwargs):
        path = path[1:]
        (m, tail) = self.modulepath(path)
        return m.read(tail, *args, **kwargs)


    def write(self, path, *args, **kwargs):
        path = path[1:]
        (m, tail) = self.modulepath(path)
        return m.write(tail, *args, **kwargs)


    def truncate(self, path, *args, **kwargs):
        path = path[1:]
        (m, tail) = self.modulepath(path)
        return m.truncate(tail, *args, **kwargs)



def main():
    usage = "Newbiecontest File System\n\n"
    usage += NewbiecontestFS.fusage

    server = NewbiecontestFS(usage = usage)
    server.parse(errex = 1)
    server.main()


if __name__ == '__main__':
    main()
