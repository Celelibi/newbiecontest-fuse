# coding: utf-8

import time
import lxml.html

import fileobjects as fo
from . import ParsingException, FSSubModuleFiles



class Challenges(FSSubModuleFiles):
    urlcat = "index.php?page=challenges"
    cachelife = 60


    def __init__(self, req):
        super(Challenges, self).__init__()
        self.req = req
        self.catexpir = None


    def updatefiles(self):
        now = time.time()
        if self.catexpir is not None and self.catexpir > now:
            return

        res = self.req.get(self.urlcat)
        doc = lxml.html.fromstring(res.content, base_url = res.url)
        tables = doc.cssselect('div#content > div.textpad > table')

        if len(tables) != 3:
            raise ParsingException()

        self.files = {}

        # Categories are linked in the first table
        tablecat = tables[0]
        for link in tablecat.cssselect('tr strong a'):
            caturl = link.get('href')
            catname = lxml.html.tostring(link, encoding = 'utf-8', method = 'text').strip()

            if not catname.startswith('Épreuves '):
                continue

            catname = catname[len('Épreuves '):]
            self.files[catname] = fo.Directory(catname)

        self.catexpir = now + self.cachelife
