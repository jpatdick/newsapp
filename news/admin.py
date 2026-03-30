"""
admin.py - Django admin configuration for the News application.
Registers all models with sensible list displays and filters.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Article, CustomUser, Newsletter, Publisher


# ---------------------------------------------------------------------------
# Publisher admin
# ---------------------------------------------------------------------------
@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ('name', 'website', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)


# ---------------------------------------------------------------------------
# Custom user admin
# ---------------------------------------------------------------------------
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'publisher', 'is_active')
    list_filter = ('role', 'publisher', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)

    # Extend the default fieldsets with our custom fields
    fieldsets = UserAdmin.fieldsets + (
        ('News App', {
            'fields': (
                'role',
                'publisher',
                'subscribed_publishers',
                'subscribed_journalists',
            )
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('News App', {
            'fields': ('role', 'publisher'),
        }),
    )


# ---------------------------------------------------------------------------
# Article admin
# ---------------------------------------------------------------------------
@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'author', 'publisher', 'approved', 'created_at'
    )
    list_filter = ('approved', 'publisher', 'created_at')
    search_fields = ('title', 'author__username', 'content')
    ordering = ('-created_at',)
    actions = ['approve_articles']

    @admin.action(description='Approve selected articles')
    def approve_articles(self, request, queryset):
        """Bulk-approve selected articles from the admin interface."""
        for article in queryset.filter(approved=False):
            article.approved = True
            article.save()  # triggers post_save signal
        self.message_user(
            request, f"{queryset.count()} article(s) approved."
        )


# ---------------------------------------------------------------------------
# Newsletter admin
# ---------------------------------------------------------------------------
@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at')
    search_fields = ('title', 'author__username')
    filter_horizontal = ('articles',)
    ordering = ('-created_at',)
