"""
models.py - Data layer for the News Application.

Database design follows 3NF normalisation:
  - CustomUser  : extends AbstractUser; role determines group membership.
  - Publisher   : organisation that employs editors and journalists.
  - Article     : content unit authored by a journalist, optionally
                  under a publisher.
  - Newsletter  : curated M2M collection of articles by a journalist.

Relationships
-------------
Publisher  --< Article       (nullable FK - publisher content)
CustomUser --< Article       (FK on author - journalist who wrote it)
CustomUser --< Newsletter    (FK on author)
Newsletter >--< Article      (M2M)
CustomUser >--< Publisher    (reader subscriptions)
CustomUser >--< CustomUser   (reader subscriptions to journalists)
"""

from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# Role constants - single source of truth used across the project
# ---------------------------------------------------------------------------


class Role(models.TextChoices):
    READER = 'reader', 'Reader'
    JOURNALIST = 'journalist', 'Journalist'
    EDITOR = 'editor', 'Editor'


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------


class Publisher(models.Model):
    """
    Represents a news organisation.
    Editors and journalists are linked via CustomUser.publisher (FK).
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Custom User
# ---------------------------------------------------------------------------


class CustomUser(AbstractUser):
    """
    Extends Django's AbstractUser with a role field and role-specific fields.

    Role-specific fields
    --------------------
    Reader     : subscribed_publishers, subscribed_journalists
    Journalist : articles and newsletters accessible via reverse FK
    Editor     : belongs to a publisher via publisher FK

    Fields irrelevant to a user's role are set to None / blank.
    """

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.READER,
    )

    # Journalists and editors belong to a publisher (nullable for readers)
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff',
        help_text="The publisher this journalist/editor works for.",
    )

    # -- Reader-only fields --------------------------------------------------
    subscribed_publishers = models.ManyToManyField(
        Publisher,
        blank=True,
        related_name='subscriber_readers',
        help_text="Publishers this reader has subscribed to.",
    )

    subscribed_journalists = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='reader_followers',
        help_text="Journalists this reader follows.",
    )

    # Resolve clashes with auth.User reverse accessors
    groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name='custom_users',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name='custom_users',
    )

    class Meta:
        ordering = ['username']

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_reader(self):
        """Return True if this user has the Reader role."""
        return self.role == Role.READER

    def is_journalist(self):
        """Return True if this user has the Journalist role."""
        return self.role == Role.JOURNALIST

    def is_editor(self):
        """Return True if this user has the Editor role."""
        return self.role == Role.EDITOR

    def save(self, *args, **kwargs):
        """
        Ensure role-specific fields are cleared for non-reader roles.
        Group assignment happens in the post_save signal (signals.py).
        """
        super().save(*args, **kwargs)

        # Journalists and editors do not use reader subscription fields;
        # clear them to keep data consistent.
        if self.role in (Role.JOURNALIST, Role.EDITOR):
            self.subscribed_publishers.clear()
            self.subscribed_journalists.clear()


# ---------------------------------------------------------------------------
# Article
# ---------------------------------------------------------------------------


class Article(models.Model):
    """
    A news article authored by a journalist.

    An article is associated with:
      - `author`    : the CustomUser (journalist) who wrote it.
      - `publisher` : optional Publisher (null = independent article).

    `approved` is set to True by an editor via the approval workflow.
    """

    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    approved = models.BooleanField(
        default=False,
        help_text="Set to True by an editor to publish the article.",
    )

    # Author must be a journalist
    author = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='authored_articles',
        help_text="The journalist who authored this article.",
    )

    # Publisher is optional; null means it is an independent article
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articles',
        help_text=(
            "Leave blank for independent (journalist-only) articles."
        ),
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = "approved" if self.approved else "pending"
        return f"[{status}] {self.title} - {self.author.username}"


# ---------------------------------------------------------------------------
# Newsletter
# ---------------------------------------------------------------------------


class Newsletter(models.Model):
    """
    A curated collection of approved articles, created by a journalist.
    Readers can view newsletters; journalists and editors can create/edit.
    """

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Author must be a journalist
    author = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='authored_newsletters',
        help_text="The journalist who curated this newsletter.",
    )

    # A newsletter contains many articles; an article can appear in many
    articles = models.ManyToManyField(
        Article,
        blank=True,
        related_name='newsletters',
        help_text="Approved articles included in this newsletter.",
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - by {self.author.username}"
