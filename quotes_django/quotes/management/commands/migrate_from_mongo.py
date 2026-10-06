"""Copy authors and quotes from the MongoDB of homework #9 into the Django database.

Expected Mongo layout (mongoengine default):
    authors: {fullname, born_date, born_location, description}
    quotes:  {quote, tags: [str], author: ObjectId -> authors._id}
"""
from bson import ObjectId
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from quotes.models import Author, Quote, Tag


class Command(BaseCommand):
    help = 'Migrate authors and quotes from MongoDB into the site database'

    def add_arguments(self, parser):
        parser.add_argument('--uri', default=settings.MONGO_URI, help='MongoDB connection string')
        parser.add_argument('--db', default=settings.MONGO_DB, help='MongoDB database name')
        parser.add_argument('--authors', default='authors', help='Authors collection')
        parser.add_argument('--quotes', default='quotes', help='Quotes collection')

    def handle(self, *args, **opts):
        client = MongoClient(opts['uri'], serverSelectionTimeoutMS=5000)
        try:
            mongo = client[opts['db']]
            mongo_authors = list(mongo[opts['authors']].find())
            mongo_quotes = list(mongo[opts['quotes']].find())
        except PyMongoError as exc:
            raise CommandError(f'Cannot read MongoDB: {exc}')
        finally:
            client.close()

        with transaction.atomic():
            authors_by_id = {}
            new_authors = 0
            for doc in mongo_authors:
                author, created = Author.objects.get_or_create(
                    fullname=doc['fullname'].strip(),
                    defaults={
                        'born_date': doc.get('born_date', ''),
                        'born_location': doc.get('born_location', ''),
                        'description': doc.get('description', ''),
                    },
                )
                authors_by_id[doc['_id']] = author
                new_authors += created

            new_quotes = skipped = 0
            for doc in mongo_quotes:
                ref = doc.get('author')
                if isinstance(ref, ObjectId):
                    author = authors_by_id.get(ref)
                elif isinstance(ref, str):  # author stored by name
                    author = Author.objects.get_or_create(fullname=ref.strip())[0]
                else:
                    author = None
                if author is None:
                    skipped += 1
                    continue

                quote, created = Quote.objects.get_or_create(
                    quote=(doc.get('quote') or doc.get('text', '')).strip(), author=author
                )
                if created:
                    quote.tags.set([Tag.objects.get_or_create(name=t.strip())[0]
                                    for t in doc.get('tags', []) if t.strip()])
                    new_quotes += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done: {new_authors} new authors, {new_quotes} new quotes, {skipped} skipped.'
        ))