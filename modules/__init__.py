# coding: utf-8

import errno
import fuse
import itertools

import fileobjects as fo



class ParsingException(BaseException):
    pass



class FSModule(object):
    """The empty module.
    It usually return -ENOENT, 0 or []"""

    def __init__(self):
        pass

    def getndirs(self):
        return 0

    def getattr(self, path):
        return -errno.ENOENT

    def readdir(self, path, offset):
        return []

    def open(self, path, *args, **kwargs):
        return -errno.ENOENT

    def read(self, path, *args, **kwargs):
        return -errno.ENOENT

    def write(self, path, *args, **kwargs):
        return -errno.ENOENT

    def truncate(self, path, *args, **kwargs):
        return -errno.ENOENT



class FSSubModule(FSModule):
    """This module can have submodules and a rootmodule. The rootmodule will
    have its files directly on the level of the instance module. The dirmodules
    will have their files inside a subdirectory.

    Attributes:
        rootmodule   The module that has its files in this level.
        dirmodules   A dict that associate a directory name with a module."""

    def __init__(self, rootmodule = None, dirmodules = {}, *args, **kwargs):
        super(FSSubModule, self).__init__(*args, **kwargs)

        self.rootmodule = rootmodule
        self.dirmodules = dirmodules

        if self.rootmodule is None:
            self.rootmodule = FSModule()


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


    def getndirs(self):
        return self.rootmodule.getndirs() + len(self.dirmodules)


    def getattr(self, path):
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
        (m, tail) = self.modulepath(path)

        if tail == "":
            f = [m.readdir(tail, offset)]
            if path == "":
                f.append(fuse.Direntry(name) for name in self.dirmodules.keys())
            return itertools.chain(*f)

        else:
            return m.readdir(tail, offset)


    def open(self, path, *args, **kwargs):
        (m, tail) = self.modulepath(path)

        if tail == "":
            return -errno.EISDIR

        return m.open(tail, *args, **kwargs)


    def read(self, path, *args, **kwargs):
        (m, tail) = self.modulepath(path)
        return m.read(tail, *args, **kwargs)


    def write(self, path, *args, **kwargs):
        (m, tail) = self.modulepath(path)
        return m.write(tail, *args, **kwargs)


    def truncate(self, path, *args, **kwargs):
        (m, tail) = self.modulepath(path)
        return m.truncate(tail, *args, **kwargs)
