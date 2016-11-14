#!/usr/bin/env python
# coding: utf-8

import errno
import fuse

import fileobjects as fo
import modules.news as news
import modules.challenges as challenges
import modules.authrequests as authrequests

fuse.fuse_python_api = (0, 2)



class NewbiecontestFS(fuse.Fuse):
    def __init__(self, *args, **kwargs):
        super(NewbiecontestFS, self).__init__(*args, **kwargs)
        self.pathmodule = {}

        req = authrequests.AuthRequests()
        self.modules = [
                authrequests.Auth(req),
                news.News(req),
                challenges.Challenges(req)
        ]

        for m in self.modules:
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

    server = NewbiecontestFS(usage = usage)
    server.parse(errex = 1)
    server.main()


if __name__ == '__main__':
    main()
