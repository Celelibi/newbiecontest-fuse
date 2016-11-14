# coding: utf-8

import requests

import fileobjects as fo



class AuthException(BaseException):
    pass



class AuthRequests(object):
    """Make all the requests through and manage the authentication and cookies.

    This class is responsible for the virtual files /username and /password."""

    urlbase = "https://www.newbiecontest.org/"
    urlauth = "forums/index.php?action=login2"

    def __init__(self):
        self.username = ''
        self.password = ''
        self.cookies = None
        self.files = {}

        uf = fo.File("username", isWritable = True)
        pf = fo.File("password", isWritable = True, content = b"<password is write-only>\n")
        df = fo.File("deauth", isWritable = True, content = b"Write 1 to this file to logout\n")

        for f in [uf, pf, df]:
            path = "/" + f.name
            self.files[path] = f


    def handledpath(self):
        return self.files.keys()


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


    def getattr(self, path):
        return self.files[path].stat


    def open(self, path, flags):
        pass


    def read(self, path, size, offset):
        return self.files[path].content[offset:offset+size]


    def write(self, path, buf, offset):
        buflen = len(buf)
        buf = buf.rstrip("\r\n")

        if path == "/username":
            self.files[path].content = bytes(buf + "\n")
            if buf != self.username:
                self.deauth()
                self.username = buf
            return buflen

        elif path == "/password":
            if buf != self.username:
                self.deauth()
                self.password = buf
            return buflen

        elif path == "/deauth":
            if int(buf):
                self.deauth()
            return buflen


    def truncate(self, path, length):
        if path == "/username":
            c = self.files[path].content
            c = c[:length] + b"\0" * (length - len(c))
            self.files[path].content = c

            if c.rstrip("\r\n") != self.username:
                self.deauth()
                self.username = c.rstrip("\r\n")

        elif path == "/password":
            c = self.password
            c = c[:length] + b"\0" * (length - len(c))

            if c != self.password:
                self.deauth()
                self.password = c

        elif path == "/deauth":
            pass




