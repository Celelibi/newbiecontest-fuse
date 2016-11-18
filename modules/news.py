# coding: utf-8

import os
import time
import datetime
import re
import lxml.html

import fileobjects as fo
from . import ParsingException, FSSubModuleFiles



class News(FSSubModuleFiles):
    urlnews = "index.php?page=news"
    newslife = 60
    datere = re.compile('^(\d+ \d+ \d+ à \d+:\d+:\d+)')


    def __init__(self, req):
        super(News, self).__init__()
        self.req = req
        self.newsexpir = None


    def updatefiles(self):
        now = time.time()
        if self.newsexpir is not None and self.newsexpir > now:
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
        self.files = {}

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
            self.files[news.name] = news
        self.newsexpir = now + self.newslife
