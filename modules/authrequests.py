# coding: utf-8

import requests
import lxml.html

import fileobjects as fo
from . import FSSubModuleFiles



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

    def write(self, buf, offset):
        self.truncate(0)
        self.content = buf
        return len(buf)

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

    def write(self, buf, offset):
        self.truncate(0)
        self.content = buf
        return len(buf)

    def truncate(self, size):
        self.content = self.cutextend(b'', size)



class Auth(FSSubModuleFiles):
    """This class is responsible for the virtual files /username, /password and
    /deauth."""

    def __init__(self, req):
        super(Auth, self).__init__()
        self.req = req
        self.files = {}

        uf = FileUsername("username", req)
        pf = FilePassword("password", req)
        df = FileDeauth("deauth", req)

        for f in [uf, pf, df]:
            self.files[f.name] = f



class AuthRequests(object):
    """Make all the requests through and manage the authentication and cookies."""

    urlbase = "https://www.newbiecontest.org/"
    urlauth = "forums/index.php?action=login2"

    def __init__(self):
        self.username = ''
        self.password = ''
        self.cookies = None


    def fullurl(self, path):
        return self.urlbase + path


    def request(self, method, url, **kwargs):
        kwargs.setdefault('allow_redirects', True)
        kwargs.setdefault('cookies', self.cookies)
        resp = requests.request(method, self.fullurl(url), **kwargs)

        if self.cookies is None:
            self.cookies = resp.cookies
        else:
            self.cookies.update(resp.cookies)
        return resp


    def get(self, *args, **kwargs):
        return self.request('get', *args, **kwargs)


    def post(self, *args, **kwargs):
        return self.request('post', *args, **kwargs)


    @staticmethod
    def is_auth(res):
        doc = lxml.html.fromstring(res.content, base_url = res.url)
        forms = doc.cssselect('div#content > div.member > form')
        if len(forms) > 0:
            return False

        infos = doc.cssselect('div#content > div.member > div#memberinfos')
        if len(infos) > 0:
            return True

        # I dunno, LOL. ¯\_(ツ)_/¯
        return False


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
