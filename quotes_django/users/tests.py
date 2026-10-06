import re

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', 'Old-pass-123')

    def request_reset(self, email='alice@example.com'):
        return self.client.post(reverse('users:password_reset'), {'email': email})

    def reset_link(self):
        return re.search(r'http://testserver(/users/reset/\S+/)', mail.outbox[-1].body).group(1)

    def test_login_page_links_to_reset(self):
        response = self.client.get(reverse('users:login'))
        self.assertContains(response, reverse('users:password_reset'))

    def test_reset_sends_email_with_link(self):
        response = self.request_reset()
        self.assertRedirects(response, reverse('users:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['alice@example.com'])
        self.assertIn('Password reset', message.subject)
        self.assertIn('/users/reset/', message.body)
        self.assertEqual(len(message.alternatives), 1)  # HTML version

    def test_unknown_email_gets_same_page_but_no_email(self):
        response = self.request_reset('nobody@example.com')
        self.assertRedirects(response, reverse('users:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_full_reset_flow(self):
        self.request_reset()
        # the link redirects to a URL with the token hidden in the session
        response = self.client.get(self.reset_link(), follow=True)
        self.assertTrue(response.context['validlink'])
        set_password_url = response.redirect_chain[-1][0]

        response = self.client.post(set_password_url, {
            'new_password1': 'Brand-new-456', 'new_password2': 'Brand-new-456',
        })
        self.assertRedirects(response, reverse('users:password_reset_complete'))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Brand-new-456'))
        response = self.client.post(reverse('users:login'),
                                    {'username': 'alice', 'password': 'Brand-new-456'})
        self.assertRedirects(response, reverse('quotes:index'))

    def test_link_works_only_once(self):
        self.request_reset()
        link = self.reset_link()
        response = self.client.get(link, follow=True)
        self.client.post(response.redirect_chain[-1][0], {
            'new_password1': 'Brand-new-456', 'new_password2': 'Brand-new-456',
        })
        self.client.logout()
        response = self.client.get(link, follow=True)
        self.assertFalse(response.context['validlink'])
        self.assertContains(response, 'Link is invalid')

    def test_invalid_token(self):
        response = self.client.get(reverse('users:password_reset_confirm',
                                           args=['MQ', 'bad-token']))
        self.assertFalse(response.context['validlink'])


class RegisterEmailTests(TestCase):
    def test_email_must_be_unique(self):
        User.objects.create_user('alice', 'alice@example.com', 'Old-pass-123')
        response = self.client.post(reverse('users:register'), {
            'username': 'alice2', 'email': 'Alice@Example.com',
            'password1': 'Very-strong-123', 'password2': 'Very-strong-123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')
        self.assertEqual(User.objects.count(), 1)