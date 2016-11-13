# coding: utf-8

import os
import stat
import time
import fuse



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



class Directory(object):
    def __init__(self, name, isWritable = True):
        self.stat = DirStat()
        if isWritable:
            self.stat.st_mode |= 0220
        self.name = name
        self._files = {}

    @property
    def files(self):
        self.stat.st_atime = int(time.time())
        return self._files

    @files.setter
    def files(self, files):
        self._files = files
        self.stat.st_size = len(files)
        self.stat.touch()
