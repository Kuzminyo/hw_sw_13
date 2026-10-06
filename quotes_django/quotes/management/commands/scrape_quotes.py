from django.core.management.base import BaseCommand

from quotes.scraper import scrape_quotes


class Command(BaseCommand):
    help = 'Scrape quotes.toscrape.com into the site database'

    def handle(self, *args, **opts):
        new_authors, new_quotes = scrape_quotes()
        self.stdout.write(self.style.SUCCESS(f'Done: {new_authors} new authors, {new_quotes} new quotes.'))