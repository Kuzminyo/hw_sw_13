"""Scrape http://quotes.toscrape.com and fill the site database."""
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.db import transaction

from .models import Author, Quote, Tag

BASE_URL = 'http://quotes.toscrape.com'


def _soup(session, url):
    response = session.get(url, timeout=15)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')


def _scrape_author(session, url):
    soup = _soup(session, url)
    return {
        'born_date': soup.select_one('.author-born-date').get_text(strip=True),
        'born_location': soup.select_one('.author-born-location').get_text(strip=True).removeprefix('in '),
        'description': soup.select_one('.author-description').get_text(strip=True),
    }


def scrape_quotes(user=None):
    """Walk all pages of the site. Returns (new_authors, new_quotes)."""
    session = requests.Session()
    authors_cache = {}
    new_authors = new_quotes = 0
    url = BASE_URL + '/'

    while url:
        soup = _soup(session, url)
        with transaction.atomic():
            for block in soup.select('div.quote'):
                fullname = block.select_one('small.author').get_text(strip=True)
                author = authors_cache.get(fullname)
                if author is None:
                    author = Author.objects.filter(fullname=fullname).first()
                    if author is None:
                        about = urljoin(BASE_URL, block.select_one('a[href^="/author/"]')['href'])
                        author = Author.objects.create(
                            fullname=fullname, created_by=user, **_scrape_author(session, about)
                        )
                        new_authors += 1
                    authors_cache[fullname] = author

                text = block.select_one('span.text').get_text(strip=True)
                quote, created = Quote.objects.get_or_create(
                    quote=text, author=author, defaults={'created_by': user}
                )
                if created:
                    quote.tags.set([Tag.objects.get_or_create(name=a.get_text(strip=True))[0]
                                    for a in block.select('a.tag')])
                    new_quotes += 1

        next_link = soup.select_one('li.next > a')
        url = urljoin(BASE_URL, next_link['href']) if next_link else None

    return new_authors, new_quotes