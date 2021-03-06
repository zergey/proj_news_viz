import csv
import datetime
import io
import os
import time
from pathlib import Path

import feedparser

from .parse_news import get_html_links
from .store import Store, Downloader

FEEDS = 'data/parser/conf/feeds.csv'
SOURCES = 'data/parser/conf/sources.csv'
DOWNLOAD_ROOT = 'data/parser/articles'
LISTS = Path('data/parser/lists/')

FEED_CACHE_TIME = 60 * 5
PAGE_CACHE_TIME = 60 * 10


def csv2string(rows):
    si = io.StringIO()
    cw = csv.writer(si)
    for row in rows:
        cw.writerow(row)
    return si.getvalue().strip('\r\n').encode('utf-8')


def build_dpid():
    dt = str(datetime.datetime.utcnow())
    return "{}/{}-{}".format(dt[:10], dt[11:19].replace(':', '_'), os.getpid())


class FeedLoader:
    def __init__(self, downloader):
        self.urls = set()
        self.downloader = downloader

    def load_feeds(self):
        with open(FEEDS, 'r') as f:
            items = [row for row in csv.reader(f)]

        for name, base_url, feed_url in items[1:]:
            if self.downloader.exists(feed_url, FEED_CACHE_TIME):
                continue
            body = self.downloader.load_url(feed_url, FEED_CACHE_TIME)
            print("Parsing feed", feed_url)
            try:
                feed = feedparser.parse(body)
            except Exception:
                print(f"Error downloading page {url}: {e}")
                continue
            for f in feed.entries:
                url = f.get('link', '')
                if not url or url in self.urls:
                    continue
                self.urls.add(url)
                pub = time.strftime('%Y-%m-%dT%H:%M:%S', f.published_parsed)
                meta = csv2string({
                    'url': url,
                    'title': f.get('title', ''),
                    'summary': f.get('summary', ''),
                    'published': pub,
                    'feed_url': feed_url
                })
                self.downloader.save_extra(url, 'meta', meta)

    def load_main_pages(self):
        with open(SOURCES, 'r') as f:
            items = [row for row in csv.reader(f, delimiter='\t')]

        for row in items[1:]:
            if len(row) < 2:
                continue
            url = row[1]
            if '://' in url:
                urls = [url]
            else:
                urls = ['http://' + url, 'https://' + url]

            for url in urls:
                if self.downloader.exists(url, PAGE_CACHE_TIME):
                    continue
                try:
                    base_url, body = self.downloader.load_url(url, PAGE_CACHE_TIME)
                except Exception as e:
                    print(f"Error downloading page {url}: {e}")
                    continue
                print("Parsing page", url)
                for found_url in get_html_links(base_url, body):
                    self.urls.add(found_url)

    def process(self):
        self.load_feeds()
        self.load_main_pages()
        if self.urls:
            dpid = build_dpid().replace('/', '-')
            with open(LISTS / f'feeds-{dpid}.txt', 'w') as f:
                f.write('\n'.join(sorted(self.urls)))
            print(f"Saved as feeds-{dpid}.txt")


if __name__ == '__main__':
    fl = FeedLoader(Downloader(Store(DOWNLOAD_ROOT)))
    fl.process()
