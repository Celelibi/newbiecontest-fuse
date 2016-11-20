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
        self.dirmodules["/news"].append(news.News(req))
        self.dirmodules["/challenges"].append(challenges.Challenges(req))


    @staticmethod
    def pathprefix(path):
        secondslashidx = path.find("/", 1)
        if secondslashidx == -1:
            secondslashidx = len(path)
        return path[:secondslashidx]


    def getattr(self, path):
        prefix = self.pathprefix(path)

        if path == "/":
            # We just need to count the number of directories in /
            st = fo.DirStat()
            st.st_nlink += len(self.dirmodules)
            for m in self.rootmodules:
                st.st_nlink += m.getndirs()
            return st

        elif path in self.dirmodules:
            # Asking for the attributes of a module directory
            # Count the number of directories in /moduledir
            st = fo.DirStat()
            for m in self.dirmodules[path]:
                st.st_nlink += m.getndirs()
            return st

        elif prefix in self.dirmodules:
            # Asking for the attributes of something inside a module directory
            # Delegate to all modules in /moduledir until one knows this file
            for m in self.dirmodules[prefix]:
                st = m.getattr(path)
                if st != -errno.ENOENT:
                    return st

        else:
            # Asking for the attributes of neither / or a module directory
            # May be a file in a root module
            for m in self.rootmodules:
                st = m.getattr(path)
                if st != -errno.ENOENT:
                    return st

        return -errno.ENOENT


    def readdir(self, path, offset):
        dotdot = [fuse.Direntry("."), fuse.Direntry("..")]
        prefix = self.pathprefix(path)

        if path == "/":
            dm = [fuse.Direntry(name[1:]) for name in self.dirmodules.keys()]
            rm = [m.readdir(path, offset) for m in self.rootmodules]
            return itertools.chain(dotdot, dm, *rm)

        elif path in self.dirmodules:
            dm = [m.readdir(path, offset) for m in self.dirmodules[path]]
            return itertools.chain(dotdot, *dm)

        elif prefix in self.dirmodules:
            mods = self.dirmodules[prefix]
        else:
            mods = self.rootmodules

        for m in mods:
            g = m.readdir(path, offset)
            if g != -errno.ENOENT:
                return g

        return -errno.ENOENT


    def open(self, path, *args, **kwargs):
        prefix = self.pathprefix(path)

        if prefix in self.dirmodules:
            mods = self.dirmodules[prefix]
        else:
            mods = self.rootmodules

        for m in mods:
            val = m.open(path, *args, **kwargs)
            if val != -errno.ENOENT:
                return val

        return -errno.ENOENT


    def read(self, path, *args, **kwargs):
        prefix = self.pathprefix(path)

        if prefix in self.dirmodules:
            mods = self.dirmodules[prefix]
        else:
            mods = self.rootmodules

        for m in mods:
            val = m.read(path, *args, **kwargs)
            if val != -errno.ENOENT:
                return val

        return -errno.ENOENT


    def write(self, path, *args, **kwargs):
        prefix = self.pathprefix(path)

        if prefix in self.dirmodules:
            mods = self.dirmodules[prefix]
        else:
            mods = self.rootmodules

        for m in mods:
            val = m.write(path, *args, **kwargs)
            if val != -errno.ENOENT:
                return val

        return -errno.ENOENT


    def truncate(self, path, *args, **kwargs):
        prefix = self.pathprefix(path)

        if prefix in self.dirmodules:
            mods = self.dirmodules[prefix]
        else:
            mods = self.rootmodules

        for m in mods:
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
