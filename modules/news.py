# coding: utf-8

import os
import errno
import time
import datetime
import re
import fuse
import lxml.html

import fileobjects as fo
from . import ParsingException



class News(object):
    newspath = "/news"
    urlnews = "index.php?page=news"
    newslife = 60
    datere = re.compile('^(\d+ \d+ \d+ à \d+:\d+:\d+)')


    def __init__(self, req):
        self.req = req
        self.newslist = None
        self.newsexpir = None


    def _getnews(self):
        now = time.time()
        if self.newslist is not None and self.newsexpir > now:
            return

        res = self.req.get(self.urlnews)
        doc = lxml.html.fromstring(res.content, base_url = res.url)
        elements = doc.cssselect('div#content > div.textpad > *')

        monthdict = {
                "Janvier" : "01", "Février" : "02", "Mars" : "03",
                "Avril" : "04", "Mai" : "05", "Juin" : "06", "Juillet" : "07",
                "Août" : "08", "Septembre" : "09", "Octobre" : "10",
                "Novembre" : "11", "Décembre" : "12"
        }
        self.newslist = {}

        for i in range(0, len(elements), 4):
            # The list end with a single <p>
            if i + 4 > len(elements):
                break

            [title, content, foot, hr] = elements[i:i+4]
            if title.tag != 'h2' or hr.tag != 'hr':
                raise ParsingException()

            # Build a File object
            titletext = title.text
            titletext = titletext.strip().replace('/', '_')
            news = fo.File(titletext)

            # Try to render the html
            try:
                import html2text
                htmlcontent = lxml.html.tostring(content, method = 'html')
                news.content = html2text.html2text(htmlcontent).encode('utf-8')
            except ImportError:
                news.content = lxml.html.tostring(content, encoding = 'utf-8', method = 'text')


            # Parse the publish date of the news and set it as the File's stat
            date = lxml.html.tostring(foot, encoding = 'utf-8', method = 'text')
            for a, n in monthdict.items():
                date = date.replace(a, n)

            # Replace "Aujourd'hui" and "Hier" with the date
            if date.startswith("Aujourd'hui"):
                today = datetime.date.today()
                date = date.replace("Aujourd'hui", today.strftime("%d %m %Y"))
            if date.startswith('Hier'):
                ystdy = datetime.date.today() - datetime.timedelta(days = 1)
                date = date.replace('Hier', ystdy.strftime("%d %m %Y"))

            match = self.datere.match(date)
            if match is None:
                raise ParsingException()

            date = match.group(1)
            date = datetime.datetime.strptime(date, "%d %m %Y à %H:%M:%S")
            news.stat.st_mtime = int(date.strftime("%s"))
            news.stat.st_ctime = news.stat.st_mtime

            # Add the File to the list
            self.newslist[self.newspath + "/" + news.name] = news
        self.newsexpir = now + self.newslife


    def getndirs(self):
        return 0


    def getattr(self, path):
        self._getnews()
        if path in self.newslist:
            return self.newslist[path].stat

        return -errno.ENOENT


    def readdir(self, path, offset):
        self._getnews()

        for f in self.newslist.values():
            yield fuse.Direntry(f.name)


    def open(self, path, flags):
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES

        self._getnews()

        if path not in self.newslist:
            return -errno.ENOENT


    def read(self, path, size, offset):
        self._getnews()
        if path in self.newslist:
            return self.newslist[path].content[offset:offset+size]
        return -errno.ENOENT
