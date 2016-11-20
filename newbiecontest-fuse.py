#!/usr/bin/env python
# coding: utf-8

import errno
import fuse
import itertools
import collections

import fileobjects as fo
import modules.news as news
import modules.challenges as challenges
import modules.authrequests as authrequests

fuse.fuse_python_api = (0, 2)



class NewbiecontestFS(fuse.Fuse):
    def __init__(self, *args, **kwargs):
        super(NewbiecontestFS, self).__init__(*args, **kwargs)
        self.rootmodules = []
        self.dirmodules = collections.defaultdict(list)

        req = authrequests.AuthRequests()

        self.rootmodules.append(authrequests.Auth(req))
        self.dirmodules["news"].append(news.News(req))
        self.dirmodules["challenges"].append(challenges.Challenges(req))


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
        return (self.rootmodules, path)


    def getattr(self, path):
        path = path[1:]
        (ms, tail) = self.modulepath(path)

        if tail == "":
            # Asking for / or a dirmodule
            st = fo.DirStat()
            for m in ms:
                st.st_nlink += m.getndirs()

            if path == "":
                st.st_nlink += len(self.dirmodules)
            return st

        else:
            # Asking for a module's content
            for m in ms:
                st = m.getattr(tail)
                if st != -errno.ENOENT:
                    return st

        return -errno.ENOENT


    def readdir(self, path, offset):
        dotdot = [fuse.Direntry("."), fuse.Direntry("..")]
        path = path[1:]
        (prefix, tail) = self.pathsplit(path)

        if path == "":
            dm = [fuse.Direntry(name) for name in self.dirmodules.keys()]
            rm = [m.readdir(path, offset) for m in self.rootmodules]
            return itertools.chain(dotdot, dm, *rm)

        elif path in self.dirmodules:
            dm = [m.readdir(tail, offset) for m in self.dirmodules[path]]
            return itertools.chain(dotdot, *dm)

        elif prefix in self.dirmodules:
            for m in self.dirmodules[prefix]:
                g = m.readdir(tail, offset)
                if g != -errno.ENOENT:
                    return g
        else:
            for m in self.rootmodules:
                g = m.readdir(path, offset)
                if g != -errno.ENOENT:
                    return g

        return -errno.ENOENT


    def open(self, path, *args, **kwargs):
        path = path[1:]
        (prefix, tail) = self.pathsplit(path)

        if prefix in self.dirmodules:
            for m in self.dirmodules[prefix]:
                val = m.open(tail, *args, **kwargs)
                if val != -errno.ENOENT:
                    return val
        else:
            for m in self.rootmodules:
                val = m.open(path, *args, **kwargs)
                if val != -errno.ENOENT:
                    return val

        return -errno.ENOENT


    def read(self, path, *args, **kwargs):
        path = path[1:]
        (prefix, tail) = self.pathsplit(path)

        if prefix in self.dirmodules:
            for m in self.dirmodules[prefix]:
                val = m.read(tail, *args, **kwargs)
                if val != -errno.ENOENT:
                    return val
        else:
            for m in self.rootmodules:
                val = m.read(path, *args, **kwargs)
                if val != -errno.ENOENT:
                    return val

        return -errno.ENOENT


    def write(self, path, *args, **kwargs):
        path = path[1:]
        (prefix, tail) = self.pathsplit(path)

        if prefix in self.dirmodules:
            for m in self.dirmodules[prefix]:
                val = m.write(tail, *args, **kwargs)
                if val != -errno.ENOENT:
                    return val
        else:
            for m in self.rootmodules:
                val = m.write(path, *args, **kwargs)
                if val != -errno.ENOENT:
                    return val

        return -errno.ENOENT


    def truncate(self, path, *args, **kwargs):
        path = path[1:]
        (prefix, tail) = self.pathsplit(path)

        if prefix in self.dirmodules:
            for m in self.dirmodules[prefix]:
                val = m.truncate(tail, *args, **kwargs)
                if val != -errno.ENOENT:
                    return val
        else:
            for m in self.rootmodules:
                val = m.truncate(path, *args, **kwargs)
                if val != -errno.ENOENT:
                    return val

        return -errno.ENOENT



def main():
    usage = "Newbiecontest File System\n\n"
    usage += NewbiecontestFS.fusage

    server = NewbiecontestFS(usage = usage)
    server.parse(errex = 1)
    server.main()


if __name__ == '__main__':
    main()
