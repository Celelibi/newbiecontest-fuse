# coding: utf-8

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
