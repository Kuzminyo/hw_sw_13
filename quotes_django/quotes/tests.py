from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Author, Quote, Tag


class QuotesSiteTests(TestCase):
    def setUp(self):
        self.author = Author.objects.create(fullname='Albert Einstein', born_date='March 14, 1879')
        self.tags = [Tag.objects.create(name=f'tag{i}') for i in range(12)]
        for i in range(15):
            q = Quote.objects.create(quote=f'Quote {i}', author=self.author)
            q.tags.set(self.tags[: (i % 12) + 1])

    def test_index_public_and_paginated(self):
        response = self.client.get(reverse('quotes:index'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 10)
        self.assertContains(response, 'Next')
        response = self.client.get(reverse('quotes:index') + '?page=2')
        self.assertEqual(len(response.context['page_obj']), 5)
        self.assertContains(response, 'Previous')

    def test_top_ten_tags(self):
        top = list(self.client.get(reverse('quotes:index')).context['top_tags'])
        self.assertEqual(len(top), 10)
        self.assertEqual(top[0].name, 'tag0')

    def test_quotes_by_tag(self):
        response = self.client.get(reverse('quotes:tag', args=['tag11']))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].paginator.count, 1)

    def test_author_page_public(self):
        response = self.client.get(reverse('quotes:author', args=[self.author.pk]))
        self.assertContains(response, 'Albert Einstein')

    def test_add_requires_login(self):
        for name in ('quotes:add_author', 'quotes:add_quote'):
            response = self.client.get(reverse(name))
            self.assertRedirects(response, reverse('users:login') + '?next=' + reverse(name))
        self.assertEqual(self.client.post(reverse('quotes:scrape')).status_code, 302)

    def test_logged_in_user_adds_author_and_quote(self):
        user = User.objects.create_user('bob', password='S3cret-pass!')
        self.client.force_login(user)
        self.client.post(reverse('quotes:add_author'), {'fullname': 'Jane Austen'})
        jane = Author.objects.get(fullname='Jane Austen')
        self.assertEqual(jane.created_by, user)
        self.client.post(reverse('quotes:add_quote'),
                         {'quote': 'New quote', 'author': jane.pk, 'tags': 'Love, books'})
        quote = Quote.objects.get(quote='New quote')
        self.assertEqual(sorted(t.name for t in quote.tags.all()), ['books', 'love'])


class AuthTests(TestCase):
    def test_register_and_login(self):
        response = self.client.post(reverse('users:register'), {
            'username': 'alice', 'email': 'alice@example.com',
            'password1': 'Very-strong-123', 'password2': 'Very-strong-123',
        })
        self.assertRedirects(response, reverse('quotes:index'))
        self.client.post(reverse('users:logout'))
        response = self.client.post(reverse('users:login'),
                                    {'username': 'alice', 'password': 'Very-strong-123'})
        self.assertRedirects(response, reverse('quotes:index'))