"""
api_views.py - Django REST Framework views for the News application.

Endpoints implemented
---------------------
GET    /api/articles/              - List all approved articles
GET    /api/articles/subscribed/   - Articles from subscribed sources
GET    /api/articles/<id>/         - Retrieve a single article
POST   /api/articles/              - Create article (journalists only)
PUT    /api/articles/<id>/         - Update article (owner / editor)
DELETE /api/articles/<id>/         - Delete article (owner / editor)
POST   /api/articles/<id>/approve/ - Approve article (editors only)

GET    /api/newsletters/           - List all newsletters
GET    /api/newsletters/<id>/      - Retrieve a single newsletter
POST   /api/newsletters/           - Create newsletter (journalists)
PUT    /api/newsletters/<id>/      - Update newsletter
DELETE /api/newsletters/<id>/      - Delete newsletter

POST   /api/approved/              - Internal approval webhook
POST   /api/register/              - Register a new user
"""

import logging

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Article, Newsletter, Publisher, Role
from .permissions import (
    IsEditor,
    IsJournalist,
    IsJournalistOrEditor,
    IsOwnerOrEditor,
)
from .serializers import (
    ArticleApprovalSerializer,
    ArticleSerializer,
    NewsletterSerializer,
    PublisherSerializer,
    RegisterSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Article list + create
# ---------------------------------------------------------------------------


class ArticleListCreateView(APIView):
    """
    GET  - Return all approved articles (any authenticated user).
    POST - Create a new article (journalists only).
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsJournalist()]
        return [IsAuthenticated()]

    def get(self, request):
        """Return a list of all approved articles."""
        articles = Article.objects.filter(
            approved=True
        ).select_related('author', 'publisher')
        serializer = ArticleSerializer(articles, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create a new article; author is forced to the current user."""
        data = request.data.copy()
        data['author'] = request.user.pk  # enforce author = current user

        serializer = ArticleSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data, status=status.HTTP_201_CREATED
            )
        return Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )


# ---------------------------------------------------------------------------
# Subscribed articles
# ---------------------------------------------------------------------------


class SubscribedArticlesView(APIView):
    """
    GET /api/articles/subscribed/
    Return approved articles from the reader's subscribed sources.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return articles from the reader's subscribed sources."""
        user = request.user

        # Only readers have subscriptions
        if user.role != Role.READER:
            return Response(
                {"detail": "Only readers have subscriptions."},
                status=status.HTTP_403_FORBIDDEN,
            )

        journalist_ids = user.subscribed_journalists.values_list(
            'id', flat=True
        )
        publisher_ids = user.subscribed_publishers.values_list(
            'id', flat=True
        )

        articles = (
            Article.objects.filter(approved=True)
            .filter(
                Q(author_id__in=journalist_ids)
                | Q(publisher_id__in=publisher_ids)
            )
            .select_related('author', 'publisher')
            .distinct()
        )

        serializer = ArticleSerializer(articles, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Article detail, update, delete
# ---------------------------------------------------------------------------


class ArticleDetailView(APIView):
    """
    GET    - Retrieve a single article (any authenticated user).
    PUT    - Update an article (editor or owning journalist).
    DELETE - Delete an article (editor or owning journalist).
    """

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsJournalistOrEditor()]

    def _get_article(self, pk):
        return get_object_or_404(Article, pk=pk)

    def get(self, request, pk):
        """Retrieve a single article by primary key."""
        article = self._get_article(pk)
        serializer = ArticleSerializer(article)
        return Response(serializer.data)

    def put(self, request, pk):
        """Update an article (editor or owning journalist only)."""
        article = self._get_article(pk)

        # Object-level permission check
        permission = IsOwnerOrEditor()
        if not permission.has_object_permission(request, self, article):
            return Response(
                {"detail": permission.message},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ArticleSerializer(
            article, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, pk):
        """Delete an article (editor or owning journalist only)."""
        article = self._get_article(pk)

        permission = IsOwnerOrEditor()
        if not permission.has_object_permission(request, self, article):
            return Response(
                {"detail": permission.message},
                status=status.HTTP_403_FORBIDDEN,
            )

        article.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Article approval
# ---------------------------------------------------------------------------


class ArticleApproveView(APIView):
    """
    POST /api/articles/<id>/approve/
    Allows an editor to approve an article for publication.
    """

    permission_classes = [IsAuthenticated, IsEditor]

    def post(self, request, pk):
        """Approve the specified article."""
        article = get_object_or_404(Article, pk=pk)

        if article.approved:
            return Response(
                {"detail": "Article is already approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        article.approved = True
        article.save()  # triggers the post_save signal in signals.py

        serializer = ArticleSerializer(article)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Internal /api/approved/ endpoint (called by the post_save signal)
# ---------------------------------------------------------------------------


class ApprovedArticleWebhookView(APIView):
    """
    POST /api/approved/
    Internal endpoint that receives approved article data from the signal.
    AllowAny because the signal sends an unauthenticated internal request.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        """Log the approved article payload received from the signal."""
        serializer = ArticleApprovalSerializer(data=request.data)
        if serializer.is_valid():
            logger.info(
                "Approved article webhook received: id=%s title='%s'",
                serializer.validated_data.get('article_id'),
                serializer.validated_data.get('title'),
            )
            return Response(
                {"detail": "Approved article logged."},
                status=status.HTTP_200_OK,
            )
        return Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )


# ---------------------------------------------------------------------------
# Newsletter list + create
# ---------------------------------------------------------------------------


class NewsletterListCreateView(APIView):
    """
    GET  - List all newsletters (any authenticated user).
    POST - Create a newsletter (journalists only).
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsJournalist()]
        return [IsAuthenticated()]

    def get(self, request):
        """Return a list of all newsletters."""
        newsletters = (
            Newsletter.objects.all()
            .select_related('author')
            .prefetch_related('articles')
        )
        serializer = NewsletterSerializer(newsletters, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create a new newsletter; author is forced to the current user."""
        data = request.data.copy()
        data['author'] = request.user.pk

        serializer = NewsletterSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data, status=status.HTTP_201_CREATED
            )
        return Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )


# ---------------------------------------------------------------------------
# Newsletter detail, update, delete
# ---------------------------------------------------------------------------


class NewsletterDetailView(APIView):
    """
    GET    - Retrieve a single newsletter.
    PUT    - Update a newsletter (editor or owning journalist).
    DELETE - Delete a newsletter (editor or owning journalist).
    """

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsJournalistOrEditor()]

    def _get_newsletter(self, pk):
        return get_object_or_404(Newsletter, pk=pk)

    def get(self, request, pk):
        """Retrieve a single newsletter by primary key."""
        newsletter = self._get_newsletter(pk)
        serializer = NewsletterSerializer(newsletter)
        return Response(serializer.data)

    def put(self, request, pk):
        """Update a newsletter (editor or owning journalist only)."""
        newsletter = self._get_newsletter(pk)

        permission = IsOwnerOrEditor()
        if not permission.has_object_permission(
            request, self, newsletter
        ):
            return Response(
                {"detail": permission.message},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = NewsletterSerializer(
            newsletter, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, pk):
        """Delete a newsletter (editor or owning journalist only)."""
        newsletter = self._get_newsletter(pk)

        permission = IsOwnerOrEditor()
        if not permission.has_object_permission(
            request, self, newsletter
        ):
            return Response(
                {"detail": permission.message},
                status=status.HTTP_403_FORBIDDEN,
            )

        newsletter.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Publisher list
# ---------------------------------------------------------------------------


class PublisherListView(APIView):
    """GET /api/publishers/ - List all publishers."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return a list of all publishers."""
        publishers = Publisher.objects.all()
        serializer = PublisherSerializer(publishers, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# User registration
# ---------------------------------------------------------------------------


class RegisterView(APIView):
    """POST /api/register/ - Register a new user account."""

    permission_classes = [AllowAny]

    def post(self, request):
        """Register a new user and return their public profile."""
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                UserSerializer(user).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )
