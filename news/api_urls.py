"""
api_urls.py - URL patterns for the REST API.

All paths are prefixed with /api/ via newsproject/urls.py.
"""

from django.urls import path

from .api_views import (
    ApprovedArticleWebhookView,
    ArticleApproveView,
    ArticleDetailView,
    ArticleListCreateView,
    NewsletterDetailView,
    NewsletterListCreateView,
    PublisherListView,
    RegisterView,
    SubscribedArticlesView,
)

urlpatterns = [
    # -- Articles ------------------------------------------------------------
    path(
        'articles/',
        ArticleListCreateView.as_view(),
        name='api-article-list',
    ),
    path(
        'articles/subscribed/',
        SubscribedArticlesView.as_view(),
        name='api-article-subscribed',
    ),
    path(
        'articles/<int:pk>/',
        ArticleDetailView.as_view(),
        name='api-article-detail',
    ),
    path(
        'articles/<int:pk>/approve/',
        ArticleApproveView.as_view(),
        name='api-article-approve',
    ),

    # -- Newsletters ---------------------------------------------------------
    path(
        'newsletters/',
        NewsletterListCreateView.as_view(),
        name='api-newsletter-list',
    ),
    path(
        'newsletters/<int:pk>/',
        NewsletterDetailView.as_view(),
        name='api-newsletter-detail',
    ),

    # -- Publishers ----------------------------------------------------------
    path(
        'publishers/',
        PublisherListView.as_view(),
        name='api-publisher-list',
    ),

    # -- Internal webhook (called by post_save signal) -----------------------
    path(
        'approved/',
        ApprovedArticleWebhookView.as_view(),
        name='api-approved-webhook',
    ),

    # -- Auth & Registration -------------------------------------------------
    path(
        'register/',
        RegisterView.as_view(),
        name='api-register',
    ),
]
