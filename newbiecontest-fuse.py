#!/usr/bin/env python
# coding: utf-8

import fuse
import itertools

import modules
import modules.news as news
import modules.challenges as challenges
import modules.authrequests as authrequests

fuse.fuse_python_api = (0, 2)




class NewbiecontestFS(fuse.Fuse):
    def __init__(self, *args, **kwargs):
        super(NewbiecontestFS, self).__init__(*args, **kwargs)

        req = authrequests.AuthRequests()
        rootmodule = authrequests.Auth(req)

        dirmodules = {}
        dirmodules["news"] = news.News(req)
        dirmodules["challenges"] = challenges.Challenges(req)

        self.rootfsmodule = modules.FSSubModule(rootmodule, dirmodules)


    def getattr(self, path):
        path = path[1:]
        return self.rootfsmodule.getattr(path)

    def readdir(self, path, offset):
        path = path[1:]
        dotdot = [fuse.Direntry("."), fuse.Direntry("..")]
        f = self.rootfsmodule.readdir(path, offset)
        return itertools.chain(dotdot, f)

    def open(self, path, *args, **kwargs):
        path = path[1:]
        return self.rootfsmodule.open(path, *args, **kwargs)

    def read(self, path, *args, **kwargs):
        path = path[1:]
        return self.rootfsmodule.read(path, *args, **kwargs)

    def write(self, path, *args, **kwargs):
        path = path[1:]
        return self.rootfsmodule.write(path, *args, **kwargs)

    def truncate(self, path, *args, **kwargs):
        path = path[1:]
        return self.rootfsmodule.truncate(path, *args, **kwargs)



def main():
    usage = "Newbiecontest File System\n\n"
    usage += NewbiecontestFS.fusage

    server = NewbiecontestFS(usage = usage)
    server.parse(errex = 1)
    server.main()


if __name__ == '__main__':
    main()
