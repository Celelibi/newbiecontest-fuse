# coding: utf-8

import time
import random
import requests
import threading
import lxml.html

import fileobjects as fo
import threadsync as th
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

        self.sem = threading.Semaphore(20)
        self.cookiesLock = th.RWLock()
        self.authComplete = th.EventTAS()
        self.authSuccess = False

        # Assume we're auth by default
        self.authComplete.set()


    def fullurl(self, path):
        return self.urlbase + path


    # Has to be called with self.cookiesLock read-locked at least
    def _request(self, method, url, **kwargs):
        kwargs.setdefault('allow_redirects', True)
        kwargs.setdefault('cookies', self.cookies)
        url = self.fullurl(url)

        for _ in range(3):
            resp = requests.request(method, url, **kwargs)
            if resp.status_code != 403:
                break

            # Sleep for 1 to 10 seconds before retrying
            time.sleep(random.randint(10, 100) / 10)
        return resp


    def request(self, method, url, auth = False, **kwargs):
        with self.sem, self.cookiesLock.read():
            resp = self._request(method, url, **kwargs)

            if not auth:
                # FIXME: Should we save the cookies?
                return resp

            if not self.is_auth(resp):
                if self.authComplete.clear():
                    # No auth in progress? We'll do it.

                    with self.cookiesLock.write():
                        try:
                            # At that point, all threads are either locked at
                            # the beginning waiting for a read on
                            # self.cookiesLock, or waiting for the
                            # authentication to complete (in the "else" below).
                            self.authSuccess = False
                            self._auth()
                            self.authSuccess = True

                        finally:
                            # This needs to be done with the write lock held in
                            # order to prevent new threads with a read lock
                            # messing with the "if self.authComplete.clear()"
                            # above.
                            self.authComplete.set()

                else:
                    # Someone else is running an authentication, just wait for it...
                    with self.cookiesLock.unlock():
                        self.authComplete.wait()

                if not self.authSuccess:
                    raise AuthException

                # Retry now we should be authenticated
                resp = self._request(method, url, **kwargs)
                if not self.is_auth(resp):
                    raise AuthException

            with self.cookiesLock.write():
                if self.cookies is None:
                    # Could only happen if a query without cookies was authenticated
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


    # Has to be called with self.cookiesLock write-locked
    def _auth(self):
        self._deauth()
        cred = {'user' : self.username, 'passwrd' : self.password}
        resp = self._request('post', self.urlauth, data = cred)

        if resp.url.endswith(self.urlauth):
            raise AuthException

        self.cookies = resp.history[0].cookies
        return resp


    def auth(self):
        with self.cookiesLock.write():
            self._auth()


    # Has to be called with self.cookiesLock write-locked
    def _deauth(self):
        self.cookies = None


    def deauth(self):
        with self.cookiesLock.write():
            self._deauth()
