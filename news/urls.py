"""
urls.py - Web UI URL patterns for the News application.
"""

from django.urls import path
from . import views

urlpatterns = [
    # -- Authentication ------------------------------------------------------
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # -- Articles (home landing page) ----------------------------------------
    path('', views.home_view, name='articles'),
    path(
        'articles/<int:pk>/',
        views.article_detail_view,
        name='article_detail',
    ),
    path(
        'articles/create/',
        views.create_article_view,
        name='create_article',
    ),
    path(
        'articles/<int:pk>/edit/',
        views.edit_article_view,
        name='edit_article',
    ),

    # -- Editor dashboard ----------------------------------------------------
    path(
        'editor/',
        views.editor_dashboard_view,
        name='editor_dashboard',
    ),
    path(
        'editor/approve/<int:pk>/',
        views.approve_article_view,
        name='approve_article',
    ),

    # -- Newsletters ---------------------------------------------------------
    path(
        'newsletters/',
        views.newsletter_list_view,
        name='newsletter_list',
    ),
    path(
        'newsletters/<int:pk>/',
        views.newsletter_detail_view,
        name='newsletter_detail',
    ),
    path(
        'newsletters/create/',
        views.create_newsletter_view,
        name='create_newsletter',
    ),
    path(
        'newsletters/<int:pk>/edit/',
        views.edit_newsletter_view,
        name='edit_newsletter',
    ),
    path(
        'newsletters/<int:pk>/delete/',
        views.delete_newsletter_view,
        name='delete_newsletter',
    ),

    # -- Publishers ----------------------------------------------------------
    path(
        'publishers/',
        views.publisher_list_view,
        name='publisher_list',
    ),
    path(
        'publishers/create/',
        views.create_publisher_view,
        name='create_publisher',
    ),
    path(
        'publishers/<int:pk>/edit/',
        views.edit_publisher_view,
        name='edit_publisher',
    ),
    path(
        'publishers/<int:pk>/subscribe/',
        views.subscribe_publisher_view,
        name='subscribe_publisher',
    ),
    path(
        'journalists/<int:pk>/follow/',
        views.subscribe_journalist_view,
        name='follow_journalist',
    ),
]
