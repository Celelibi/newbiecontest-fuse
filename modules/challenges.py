# coding: utf-8

import errno
import time
import fuse
import lxml.html

import fileobjects as fo
from . import ParsingException



class Challenges(object):
    urlcat = "index.php?page=challenges"
    cachelife = 60


    class Category(object):
        def __init__(self, name, link = None):
            self.name = name
            self.link = link
            self.dir = fo.Directory(name)


    def __init__(self, req):
        self.req = req
        self.catdirs = None
        self.catexpir = None


    def _getcategories(self):
        now = time.time()
        if self.catdirs is not None and self.catexpir > now:
            return

        res = self.req.get(self.urlcat)
        doc = lxml.html.fromstring(res.content, base_url = res.url)
        tables = doc.cssselect('div#content > div.textpad > table')

        if len(tables) != 3:
            raise ParsingException()

        self.catdirs = {}

        # Categories are linked in the first table
        tablecat = tables[0]
        for link in tablecat.cssselect('tr strong a'):
            caturl = link.get('href')
            catname = lxml.html.tostring(link, encoding = 'utf-8', method = 'text').strip()

            if not catname.startswith('Épreuves '):
                continue

            catname = catname[len('Épreuves '):]
            self.catdirs[catname] = self.Category(catname, caturl)

        self.catexpir = now + self.cachelife


    def getndirs(self):
        self._getcategories()
        return len(self.catdirs)


    def getattr(self, path):
        self._getcategories()

        if path in self.catdirs:
            return self.catdirs[path].dir.stat

        return -errno.ENOENT


    def readdir(self, path, offset):
        self._getcategories()

        for f in self.catdirs.values():
            yield fuse.Direntry(f.name)
