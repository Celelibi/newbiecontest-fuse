# coding: utf-8

import errno
import requests

import fileobjects as fo



class AuthException(BaseException):
    pass



class FileUsername(fo.File):
    def __init__(self, name, auth, **kwargs):
        kwargs.setdefault('isWritable', True)
        super(FileUsername, self).__init__(name, **kwargs)
        self.auth = auth

    @fo.File.content.setter
    def content(self, val):
        fo.File.content.fset(self, val)
        # rstrip only for auth, not for the content of the file.
        val = val.rstrip("\r\n")

        if val != self.auth.username:
            self.auth.deauth()
            self.auth.username = val



class FilePassword(fo.File):
    def __init__(self, name, auth, **kwargs):
        kwargs.setdefault('isWritable', True)
        kwargs.setdefault('content', b"<password is write-only>\n")
        super(FilePassword, self).__init__(name, **kwargs)
        self.auth = auth

    @fo.File.content.setter
    def content(self, val):
        # We don't actually modify the content, we just set the auth password
        val = val.rstrip("\r\n")

        if val != self.auth.password:
            self.auth.deauth()
            self.auth.password = val

        self.stat.touch()

    def truncate(self, size):
        self.content = self.cutextend(self.auth.password, size)



class FileDeauth(fo.File):
    def __init__(self, name, auth, **kwargs):
        kwargs.setdefault('isWritable', True)
        kwargs.setdefault('content', b"<Write 1 to this file to logout>\n")
        super(FileDeauth, self).__init__(name, **kwargs)
        self.auth = auth

    @fo.File.content.setter
    def content(self, val):
        try:
            if int(val):
                self.auth.deauth()
        except ValueError:
            pass

    def truncate(self, size):
        self.content = self.cutextend(b'', size)



class Auth(object):
    """This class is responsible for the virtual files /username, /password and
    /deauth."""

    def __init__(self, req):
        self.req = req
        self.files = {}

        uf = FileUsername("username", req)
        pf = FilePassword("password", req)
        df = FileDeauth("deauth", req)

        for f in [uf, pf, df]:
            path = "/" + f.name
            self.files[path] = f


    def handledpath(self):
        return self.files.keys()


    def getattr(self, path):
        return self.files[path].stat


    def open(self, path, flags):
        if path not in self.files:
            # Should not happen
            return -errno.ENOENT

        return None


    def read(self, path, size, offset):
        return self.files[path].content[offset:offset+size]


    def write(self, path, buf, offset):
        self.files[path].content = bytes(buf)
        return len(buf)


    def truncate(self, path, length):
        self.files[path].truncate(length)



class AuthRequests(object):
    """Make all the requests through and manage the authentication and cookies."""

    urlbase = "https://www.newbiecontest.org/"
    urlauth = "forums/index.php?action=login2"

    def __init__(self):
        self.username = ''
        self.password = ''
        self.cookies = None


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
