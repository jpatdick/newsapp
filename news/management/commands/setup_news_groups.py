"""
Management command: setup_news_groups

Usage: python manage.py setup_news_groups

Creates the Reader, Journalist, and Editor groups with the correct
permissions. Safe to run multiple times (idempotent).
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create role-based groups (Reader, Journalist, Editor).'

    def handle(self, *args, **options):
        """Set up groups and assign permissions."""
        from news.signals import setup_groups
        setup_groups()
        self.stdout.write(
            self.style.SUCCESS(
                'Groups and permissions configured successfully.'
            )
        )
