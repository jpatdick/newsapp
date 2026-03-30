"""
tests.py - Automated unit tests for the News application REST API.

Test coverage
-------------
1.  AuthenticationTests      - Token obtain, invalid credentials, register
2.  RolePermissionTests      - Each role can/cannot access endpoints
3.  ArticleListTests         - GET /api/articles/
4.  ArticleCreateTests       - POST /api/articles/ (journalist only)
5.  ArticleDetailTests       - GET /api/articles/<id>/
6.  ArticleUpdateTests       - PUT /api/articles/<id>/
7.  ArticleDeleteTests       - DELETE /api/articles/<id>/
8.  ArticleApproveTests      - POST /api/articles/<id>/approve/
9.  SubscribedArticlesTests  - GET /api/articles/subscribed/
10. NewsletterTests          - CRUD for newsletters
11. SignalAndEmailTests      - Approval signal triggers email (mocked)
12. ApprovedWebhookTests     - POST /api/approved/ internal endpoint
"""

from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import Article, CustomUser, Newsletter, Publisher, Role
from .signals import setup_groups


# ---------------------------------------------------------------------------
# Base test case: shared helpers for creating test data
# ---------------------------------------------------------------------------


class BaseTestCase(TestCase):
    """
    Provides helper methods and common fixtures.
    setup_groups() is called once per test to ensure permissions exist.
    """

    def setUp(self):
        """Create groups and a standard set of users before each test."""
        # Ensure role groups and permissions exist
        setup_groups()

        # Create a publisher for use in tests
        self.publisher = Publisher.objects.create(name="Test Publisher")

        # Create one user of each role
        self.reader = self._create_user('reader_user', Role.READER)
        self.journalist = self._create_user(
            'journalist_user', Role.JOURNALIST
        )
        self.editor = self._create_user('editor_user', Role.EDITOR)

        # API client shared across tests
        self.client = APIClient()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_user(self, username, role, publisher=None, email=None):
        """Create and return a CustomUser with the given role."""
        user = CustomUser.objects.create_user(
            username=username,
            password='TestPass123!',
            role=role,
            publisher=publisher,
            email=email or f"{username}@test.com",
        )
        return user

    def _create_article(
        self,
        author,
        publisher=None,
        approved=False,
        title="Test Article",
    ):
        """Create and return an Article."""
        return Article.objects.create(
            title=title,
            content="Article content for testing purposes.",
            author=author,
            publisher=publisher,
            approved=approved,
        )

    def _create_newsletter(self, author, title="Test Newsletter"):
        """Create and return a Newsletter."""
        return Newsletter.objects.create(
            title=title,
            description="Newsletter description.",
            author=author,
        )

    def _authenticate_as(self, user):
        """Obtain a JWT token and set it on the API client."""
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': user.username, 'password': 'TestPass123!'},
            format='json',
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Could not authenticate {user.username}: {response.data}",
        )
        token = response.data['access']
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        return token

    def _clear_auth(self):
        """Remove authentication credentials from the API client."""
        self.client.credentials()


# ===========================================================================
# 1. Authentication Tests
# ===========================================================================


class AuthenticationTests(BaseTestCase):
    """Tests for JWT token acquisition and user registration."""

    def test_obtain_token_valid_credentials(self):
        """Valid credentials should return access and refresh tokens."""
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'reader_user', 'password': 'TestPass123!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_obtain_token_invalid_credentials(self):
        """Invalid credentials should return 401 Unauthorized."""
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'reader_user', 'password': 'WrongPassword!'},
            format='json',
        )
        self.assertEqual(
            response.status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_register_new_user(self):
        """Registering a new user should return 201 with user data."""
        payload = {
            'username': 'new_reader',
            'email': 'new_reader@test.com',
            'first_name': 'New',
            'last_name': 'Reader',
            'role': Role.READER,
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        response = self.client.post(
            reverse('api-register'), payload, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED
        )
        self.assertEqual(response.data['username'], 'new_reader')

    def test_register_mismatched_passwords(self):
        """Mismatched passwords should return 400 Bad Request."""
        payload = {
            'username': 'bad_user',
            'email': 'bad@test.com',
            'role': Role.READER,
            'password': 'StrongPass123!',
            'password2': 'DifferentPass!',
        }
        response = self.client.post(
            reverse('api-register'), payload, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_unauthenticated_access_to_articles_is_rejected(self):
        """Accessing /api/articles/ without a token should return 401."""
        self._clear_auth()
        response = self.client.get(reverse('api-article-list'))
        self.assertEqual(
            response.status_code, status.HTTP_401_UNAUTHORIZED
        )


# ===========================================================================
# 2. Role Permission Tests
# ===========================================================================


class RolePermissionTests(BaseTestCase):
    """Verify that group permissions are assigned correctly per role."""

    def test_reader_group_has_view_permissions_only(self):
        """Reader group should have view but not add/change/delete."""
        group = Group.objects.get(name='Reader')
        perms = set(
            group.permissions.values_list('codename', flat=True)
        )
        self.assertIn('view_article', perms)
        self.assertIn('view_newsletter', perms)
        self.assertNotIn('add_article', perms)
        self.assertNotIn('change_article', perms)
        self.assertNotIn('delete_article', perms)

    def test_journalist_group_has_full_permissions(self):
        """Journalist group should have all CRUD permissions."""
        group = Group.objects.get(name='Journalist')
        perms = set(
            group.permissions.values_list('codename', flat=True)
        )
        for codename in [
            'view_article', 'add_article',
            'change_article', 'delete_article',
        ]:
            self.assertIn(codename, perms)

    def test_editor_group_has_view_change_delete(self):
        """Editor group should not have add_article but should have rest."""
        group = Group.objects.get(name='Editor')
        perms = set(
            group.permissions.values_list('codename', flat=True)
        )
        self.assertNotIn('add_article', perms)
        for codename in [
            'view_article', 'change_article', 'delete_article'
        ]:
            self.assertIn(codename, perms)

    def test_user_assigned_to_correct_group_on_creation(self):
        """A new user should be added to the group matching their role."""
        journalist = self._create_user('new_journalist', Role.JOURNALIST)
        group_names = list(
            journalist.groups.values_list('name', flat=True)
        )
        self.assertIn('Journalist', group_names)
        self.assertNotIn('Reader', group_names)
        self.assertNotIn('Editor', group_names)


# ===========================================================================
# 3. Article List Tests
# ===========================================================================


class ArticleListTests(BaseTestCase):
    """Tests for GET /api/articles/ - list of approved articles."""

    def setUp(self):
        super().setUp()
        self.approved_article = self._create_article(
            self.journalist, approved=True, title="Approved Article"
        )
        self.unapproved_article = self._create_article(
            self.journalist, approved=False, title="Unapproved Article"
        )

    def test_reader_sees_only_approved_articles(self):
        """GET /api/articles/ should return only approved articles."""
        self._authenticate_as(self.reader)
        response = self.client.get(reverse('api-article-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [a['title'] for a in response.data['results']]
        self.assertIn('Approved Article', titles)
        self.assertNotIn('Unapproved Article', titles)

    def test_journalist_can_access_article_list(self):
        """Any authenticated journalist can GET the article list."""
        self._authenticate_as(self.journalist)
        response = self.client.get(reverse('api-article-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ===========================================================================
# 4. Article Create Tests
# ===========================================================================


class ArticleCreateTests(BaseTestCase):
    """Tests for POST /api/articles/ - article creation."""

    def test_journalist_can_create_article(self):
        """A journalist should be able to POST a new article."""
        self._authenticate_as(self.journalist)
        payload = {
            'title': 'New Article by Journalist',
            'content': 'Article content here.',
            'author': self.journalist.pk,
        }
        response = self.client.post(
            reverse('api-article-list'), payload, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED
        )
        self.assertEqual(
            response.data['title'], 'New Article by Journalist'
        )

    def test_reader_cannot_create_article(self):
        """A reader should receive 403 when trying to POST an article."""
        self._authenticate_as(self.reader)
        payload = {
            'title': 'Unauthorised Article',
            'content': 'This should not be created.',
            'author': self.reader.pk,
        }
        response = self.client.post(
            reverse('api-article-list'), payload, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN
        )

    def test_editor_cannot_create_article(self):
        """An editor should receive 403 when trying to POST an article."""
        self._authenticate_as(self.editor)
        payload = {
            'title': 'Editor Article',
            'content': 'Editors cannot create articles.',
            'author': self.editor.pk,
        }
        response = self.client.post(
            reverse('api-article-list'), payload, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN
        )

    def test_article_created_without_publisher_is_independent(self):
        """Article with no publisher should be saved with publisher=None."""
        self._authenticate_as(self.journalist)
        payload = {
            'title': 'Independent Article',
            'content': 'No publisher attached.',
            'author': self.journalist.pk,
        }
        response = self.client.post(
            reverse('api-article-list'), payload, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED
        )
        article = Article.objects.get(pk=response.data['id'])
        self.assertIsNone(article.publisher)


# ===========================================================================
# 5. Article Detail Tests
# ===========================================================================


class ArticleDetailTests(BaseTestCase):
    """Tests for GET /api/articles/<id>/."""

    def setUp(self):
        super().setUp()
        self.article = self._create_article(
            self.journalist, approved=True
        )

    def test_authenticated_user_can_retrieve_article(self):
        """Any authenticated user can retrieve a specific article."""
        self._authenticate_as(self.reader)
        url = reverse('api-article-detail', kwargs={'pk': self.article.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], self.article.title)

    def test_unauthenticated_user_cannot_retrieve_article(self):
        """Unauthenticated request to article detail returns 401."""
        self._clear_auth()
        url = reverse(
            'api-article-detail', kwargs={'pk': self.article.pk}
        )
        response = self.client.get(url)
        self.assertEqual(
            response.status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_nonexistent_article_returns_404(self):
        """Requesting an article that does not exist returns 404."""
        self._authenticate_as(self.reader)
        url = reverse('api-article-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(
            response.status_code, status.HTTP_404_NOT_FOUND
        )


# ===========================================================================
# 6. Article Update Tests
# ===========================================================================


class ArticleUpdateTests(BaseTestCase):
    """Tests for PUT /api/articles/<id>/ - update an article."""

    def setUp(self):
        super().setUp()
        self.article = self._create_article(
            self.journalist, approved=False
        )
        self.url = reverse(
            'api-article-detail', kwargs={'pk': self.article.pk}
        )

    def test_owning_journalist_can_update_article(self):
        """The authoring journalist should be able to update an article."""
        self._authenticate_as(self.journalist)
        response = self.client.put(
            self.url, {'title': 'Updated Title'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Title')

    def test_editor_can_update_any_article(self):
        """An editor should be able to update any article."""
        self._authenticate_as(self.editor)
        response = self.client.put(
            self.url, {'title': 'Editor Updated Title'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_reader_cannot_update_article(self):
        """A reader should receive 403 when attempting to update."""
        self._authenticate_as(self.reader)
        response = self.client.put(
            self.url, {'title': 'Reader Title'}, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN
        )

    def test_other_journalist_cannot_update_article(self):
        """A journalist who did not author the article gets 403."""
        other_journalist = self._create_user(
            'other_journalist', Role.JOURNALIST
        )
        self._authenticate_as(other_journalist)
        response = self.client.put(
            self.url, {'title': 'Hijacked Title'}, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN
        )


# ===========================================================================
# 7. Article Delete Tests
# ===========================================================================


class ArticleDeleteTests(BaseTestCase):
    """Tests for DELETE /api/articles/<id>/."""

    def test_owning_journalist_can_delete_article(self):
        """The authoring journalist should be able to delete their article."""
        article = self._create_article(self.journalist)
        self._authenticate_as(self.journalist)
        url = reverse(
            'api-article-detail', kwargs={'pk': article.pk}
        )
        response = self.client.delete(url)
        self.assertEqual(
            response.status_code, status.HTTP_204_NO_CONTENT
        )
        self.assertFalse(Article.objects.filter(pk=article.pk).exists())

    def test_editor_can_delete_any_article(self):
        """An editor should be able to delete any article."""
        article = self._create_article(self.journalist)
        self._authenticate_as(self.editor)
        url = reverse(
            'api-article-detail', kwargs={'pk': article.pk}
        )
        response = self.client.delete(url)
        self.assertEqual(
            response.status_code, status.HTTP_204_NO_CONTENT
        )

    def test_reader_cannot_delete_article(self):
        """A reader should receive 403 when trying to delete."""
        article = self._create_article(self.journalist)
        self._authenticate_as(self.reader)
        url = reverse(
            'api-article-detail', kwargs={'pk': article.pk}
        )
        response = self.client.delete(url)
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN
        )


# ===========================================================================
# 8. Article Approve Tests
# ===========================================================================


class ArticleApproveTests(BaseTestCase):
    """Tests for POST /api/articles/<id>/approve/ - editor approval."""

    def setUp(self):
        super().setUp()
        self.article = self._create_article(
            self.journalist, approved=False
        )
        self.url = reverse(
            'api-article-approve', kwargs={'pk': self.article.pk}
        )

    @patch('news.signals._post_to_approved_endpoint')
    @patch('news.signals._notify_subscribers')
    def test_editor_can_approve_article(self, mock_notify, mock_post):
        """An editor should be able to approve a pending article."""
        self._authenticate_as(self.editor)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.article.refresh_from_db()
        self.assertTrue(self.article.approved)

    def test_reader_cannot_approve_article(self):
        """A reader should receive 403 when trying to approve."""
        self._authenticate_as(self.reader)
        response = self.client.post(self.url)
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN
        )

    def test_journalist_cannot_approve_article(self):
        """A journalist should receive 403 when trying to approve."""
        self._authenticate_as(self.journalist)
        response = self.client.post(self.url)
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN
        )

    @patch('news.signals._post_to_approved_endpoint')
    @patch('news.signals._notify_subscribers')
    def test_approving_already_approved_article_returns_400(
        self, mock_notify, mock_post
    ):
        """Approving an already-approved article should return 400."""
        self.article.approved = True
        self.article.save()
        self._authenticate_as(self.editor)
        response = self.client.post(self.url)
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST
        )


# ===========================================================================
# 9. Subscribed Articles Tests
# ===========================================================================


class SubscribedArticlesTests(BaseTestCase):
    """
    Tests for GET /api/articles/subscribed/
    Readers should only see articles from journalists/publishers they follow.
    """

    def setUp(self):
        super().setUp()
        # A second journalist the reader does NOT follow
        self.journalist2 = self._create_user(
            'journalist2', Role.JOURNALIST
        )

        # Article from journalist (subscribed)
        self.subscribed_article = self._create_article(
            self.journalist,
            approved=True,
            title="Followed Journalist Article",
        )
        # Article from journalist2 (not subscribed)
        self.unsubscribed_article = self._create_article(
            self.journalist2,
            approved=True,
            title="Unfollowed Journalist Article",
        )

        # Reader subscribes to journalist only
        self.reader.subscribed_journalists.add(self.journalist)

    def test_reader_sees_only_subscribed_articles(self):
        """Reader should only see articles from followed journalists."""
        self._authenticate_as(self.reader)
        response = self.client.get(reverse('api-article-subscribed'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [a['title'] for a in response.data['results']]
        self.assertIn('Followed Journalist Article', titles)
        self.assertNotIn('Unfollowed Journalist Article', titles)

    def test_reader_with_publisher_subscription_sees_publisher_articles(
        self
    ):
        """Reader subscribed to a publisher sees publisher articles."""
        publisher_article = self._create_article(
            self.journalist2,
            publisher=self.publisher,
            approved=True,
            title="Publisher Article",
        )
        self.reader.subscribed_publishers.add(self.publisher)

        self._authenticate_as(self.reader)
        response = self.client.get(reverse('api-article-subscribed'))
        titles = [a['title'] for a in response.data['results']]
        self.assertIn('Publisher Article', titles)

    def test_journalist_cannot_access_subscribed_endpoint(self):
        """A journalist should receive 403 from the subscribed endpoint."""
        self._authenticate_as(self.journalist)
        response = self.client.get(reverse('api-article-subscribed'))
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN
        )

    def test_reader_with_no_subscriptions_sees_empty_list(self):
        """A reader with no subscriptions should receive an empty list."""
        empty_reader = self._create_user('empty_reader', Role.READER)
        self._authenticate_as(empty_reader)
        response = self.client.get(reverse('api-article-subscribed'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)


# ===========================================================================
# 10. Newsletter Tests
# ===========================================================================


class NewsletterTests(BaseTestCase):
    """Tests for newsletter CRUD endpoints."""

    def setUp(self):
        super().setUp()
        self.approved_article = self._create_article(
            self.journalist, approved=True
        )
        self.newsletter = self._create_newsletter(self.journalist)

    def test_any_authenticated_user_can_list_newsletters(self):
        """GET /api/newsletters/ should be accessible to all users."""
        self._authenticate_as(self.reader)
        response = self.client.get(reverse('api-newsletter-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_journalist_can_create_newsletter(self):
        """A journalist should be able to POST a new newsletter."""
        self._authenticate_as(self.journalist)
        payload = {
            'title': 'My Newsletter',
            'description': 'A great read.',
            'author': self.journalist.pk,
            'articles': [self.approved_article.pk],
        }
        response = self.client.post(
            reverse('api-newsletter-list'), payload, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED
        )

    def test_reader_cannot_create_newsletter(self):
        """A reader should receive 403 when trying to POST a newsletter."""
        self._authenticate_as(self.reader)
        payload = {
            'title': 'Unauthorised Newsletter',
            'author': self.reader.pk,
        }
        response = self.client.post(
            reverse('api-newsletter-list'), payload, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN
        )

    def test_editor_can_update_newsletter(self):
        """An editor should be able to PUT a newsletter."""
        self._authenticate_as(self.editor)
        url = reverse(
            'api-newsletter-detail', kwargs={'pk': self.newsletter.pk}
        )
        response = self.client.put(
            url, {'title': 'Editor Updated Newsletter'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_reader_cannot_delete_newsletter(self):
        """A reader should receive 403 when trying to DELETE a newsletter."""
        self._authenticate_as(self.reader)
        url = reverse(
            'api-newsletter-detail', kwargs={'pk': self.newsletter.pk}
        )
        response = self.client.delete(url)
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN
        )

    def test_journalist_can_delete_own_newsletter(self):
        """A journalist should be able to DELETE their own newsletter."""
        self._authenticate_as(self.journalist)
        url = reverse(
            'api-newsletter-detail', kwargs={'pk': self.newsletter.pk}
        )
        response = self.client.delete(url)
        self.assertEqual(
            response.status_code, status.HTTP_204_NO_CONTENT
        )


# ===========================================================================
# 11. Signal and Email Tests
# ===========================================================================


class SignalAndEmailTests(BaseTestCase):
    """
    Tests verifying that the post_save signal on Article:
      - Sends an email to subscribers when an article is approved.
      - POSTs to /api/approved/ when an article is approved.
    Uses unittest.mock to avoid real network or email calls.
    """

    def setUp(self):
        super().setUp()
        self.article = self._create_article(
            self.journalist, approved=False
        )
        # Reader subscribes to the journalist
        self.reader.subscribed_journalists.add(self.journalist)
        self.reader.email = 'reader@test.com'
        self.reader.save()

    @patch('news.signals._post_to_approved_endpoint')
    @patch('news.signals.send_mail')
    def test_email_sent_to_subscribers_on_approval(
        self, mock_send_mail, mock_post
    ):
        """Approving an article triggers send_mail to the subscriber."""
        self.article.approved = True
        self.article.save()

        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args
        recipient_list = (
            call_kwargs[1].get('recipient_list') or call_kwargs[0][3]
        )
        self.assertIn('reader@test.com', recipient_list)

    @patch('news.signals._notify_subscribers')
    @patch('news.signals._post_to_approved_endpoint')
    def test_post_to_approved_endpoint_called_on_approval(
        self, mock_post, mock_notify
    ):
        """Approving an article calls _post_to_approved_endpoint."""
        self.article.approved = True
        self.article.save()

        mock_post.assert_called_once_with(self.article)

    @patch('news.signals._post_to_approved_endpoint')
    @patch('news.signals._notify_subscribers')
    def test_signal_not_fired_for_unapproved_save(
        self, mock_notify, mock_post
    ):
        """
        Saving an article that remains unapproved should not trigger
        the email or POST actions.
        """
        self.article.title = "Updated Title"
        self.article.save()  # approved is still False

        mock_notify.assert_not_called()
        mock_post.assert_not_called()

    @patch('news.signals._post_to_approved_endpoint')
    @patch('news.signals.send_mail')
    def test_no_email_when_no_subscribers(
        self, mock_send_mail, mock_post
    ):
        """
        If no readers subscribe to the journalist, send_mail should
        not be called.
        """
        lone_journalist = self._create_user(
            'lone_journalist', Role.JOURNALIST
        )
        article = self._create_article(lone_journalist, approved=False)
        article.approved = True
        article.save()

        mock_send_mail.assert_not_called()


# ===========================================================================
# 12. Approved Webhook Endpoint Tests
# ===========================================================================


class ApprovedWebhookTests(BaseTestCase):
    """Tests for the internal POST /api/approved/ endpoint."""

    def test_valid_payload_returns_200(self):
        """A valid approval payload should return 200 OK."""
        payload = {
            'article_id': 1,
            'title': 'Approved Article',
            'author': 'journalist_user',
            'publisher': None,
            'approved': True,
        }
        response = self.client.post(
            reverse('api-approved-webhook'), payload, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_payload_returns_400(self):
        """A payload missing required fields should return 400."""
        payload = {'approved': True}  # missing 'title' and 'author'
        response = self.client.post(
            reverse('api-approved-webhook'), payload, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_endpoint_accessible_without_authentication(self):
        """
        The /api/approved/ endpoint should accept unauthenticated
        requests (AllowAny) since the signal sends the POST without
        a user token.
        """
        self._clear_auth()
        payload = {
            'article_id': 99,
            'title': 'Internal Post',
            'author': 'journalist_user',
            'publisher': 'Test Publisher',
            'approved': True,
        }
        response = self.client.post(
            reverse('api-approved-webhook'), payload, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
