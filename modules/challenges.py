# coding: utf-8

import time
import re
import lxml.html

from . import ParsingException, FSSubModuleFiles



class Challenge(FSSubModuleFiles):
    def __init__(self, req, name, url, devnull, valids, pts, note, date):
        super(Challenge, self).__init__()
        self.req = req
        self.name = name
        self.url = url
        self.devnull = devnull
        self.valids = valids
        self.pts = pts
        self.note = note
        self.date = date



class Category(FSSubModuleFiles):
    cachelife = 60
    validsre = re.compile('^doGraph\((\d+),')
    ptsre = re.compile('^(\d+) point')
    votere = re.compile('^([0-9.]+) / 10')


    def __init__(self, req, url, nchalls):
        super(Category, self).__init__()
        self.req = req
        self.url = url
        self.nchalls = nchalls
        self.cacheexpir = None


    def updatefiles(self):
        now = time.time()
        if self.cacheexpir is not None and self.cacheexpir > now:
            return

        res = self.req.get(self.url)
        doc = lxml.html.fromstring(res.content, base_url = res.url)
        tables = doc.cssselect('div#content > div.textpad > table')

        # There might be table before the right one for the newest challenges
        table = tables[-1]

        self.dirmodules = {}

        for row in table.cssselect('tr'):
            # The first row only contains the column headers
            if len(row.cssselect('th')) > 0:
                continue

            [tdlink, tdvalids, tdpts, tdvote, tddate] = row.cssselect('td')

            # Parse link and challenge name
            [link] = tdlink.cssselect('a')
            challname = lxml.html.tostring(link, encoding = 'utf-8', method = 'text')
            challname = challname.replace('/', '_')
            challurl = link.get('href')
            devnull = (len(link.cssselect('.strike')) > 0)

            # Parse validations
            [script] = tdvalids.cssselect('script')
            match = self.validsre.match(script.text)
            validscnt = int(match.group(1))

            # Parse points
            match = self.ptsre.match(tdpts.text)
            points = int(match.group(1))

            # Parse votes
            [img] = tdvote.cssselect('img')
            match = self.votere.match(img.get('title'))
            votes = float(match.group(1))

            # Parse date
            date = time.strptime(tddate.text, "%d/%m/%Y")
            date = time.mktime(date)

            self.dirmodules[challname] = Challenge(self.req, challname,
                    challurl, devnull, validscnt, points, votes, date)

        self.nchalls = len(self.dirmodules)
        self.cacheexpir = now + self.cachelife


    def getndirs(self):
        return self.nchalls



class Challenges(FSSubModuleFiles):
    urlcat = "index.php?page=challenges"
    cachelife = 60
    nchallsre = re.compile('^\d+ / (\d+)')


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

        self.dirmodules = {}

        # Categories are linked in the first table
        tablecat = tables[0]

        for row in tablecat.cssselect('tr'):
            [tdlink, tdcount] = row.cssselect('td')

            # Parse the link and category name
            [link] = tdlink.cssselect('strong a')
            caturl = link.get('href')
            catname = lxml.html.tostring(link, encoding = 'utf-8', method = 'text').strip()

            if catname.startswith('Épreuves '):
                catname = catname[len('Épreuves '):]

            # Parse the challenge count
            nchalls = lxml.html.tostring(tdcount, encoding = 'utf-8', method = 'text')
            match = self.nchallsre.match(nchalls)
            nchalls = int(match.group(1))


            self.dirmodules[catname] = Category(self.req, caturl, nchalls)

        self.catexpir = now + self.cachelife
