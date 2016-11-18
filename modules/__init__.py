# coding: utf-8

import errno
import stat
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



class FSSubModuleFiles(FSSubModule):
    """This class handles submodules as well as files, it is ment to be
    inherited to override at least the method updatefiles.

    Attributes:
        files    A dict that associate nales to any subclass of File or
                 Directory."""

    def __init__(self, *args, **kwargs):
        self.superself = super(FSSubModuleFiles, self)
        self.superself.__init__(*args, **kwargs)
        self.files = {}


    def updatefiles(self):
        pass


    def getndirs(self):
        self.updatefiles()

        count = 0
        for f in self.files.values():
            if f.stat.st_mode & stat.S_IFDIR:
                count += 1
        return count + self.superself.getndirs()


    def getattr(self, path):
        self.updatefiles()
        if path in self.files:
            return self.files[path].stat

        return self.superself.getattr(path)


    def readdir(self, path, offset):
        self.updatefiles()

        otherfiles = self.superself.readdir(path, offset)
        if path != "":
            return otherfiles

        myfiles = (fuse.Direntry(f.name) for f in self.files.values())
        return itertools.chain(otherfiles, myfiles)


    def open(self, path, flags):
        self.updatefiles()

        if path not in self.files:
            return self.superself.open(path, flags)


    def read(self, path, size, offset):
        self.updatefiles()
        if path in self.files:
            return self.files[path].read(size, offset)
        return self.superself.read(path, size, offset)


    def write(self, path, buf, offset):
        self.updatefiles()
        if path in self.files:
            return self.files[path].write(buf, offset)
        return self.superself.write(path, buf, offset)


    def truncate(self, path, length):
        self.updatefiles()
        if path in self.files:
            self.files[path].truncate(length)
            return None
        return self.superself.truncate(path, length)
