"""
signals.py - Django signal handlers for the News application.

Two responsibilities
--------------------
1. assign_user_group (post_save on CustomUser)
   Automatically adds the user to the correct Django auth Group
   (Reader / Journalist / Editor) whenever a user is created or their
   role changes. Groups and permissions are created here if they do not
   yet exist.

2. article_approved (post_save on Article)
   Fires when an Article record is saved. When the article transitions
   to approved=True for the FIRST TIME, this handler:

   a) Emails every subscriber of the article's journalist or publisher.
   b) POSTs the approved article payload to /api/approved/ for logging.

   The handler tracks first-time approval using the 'created' flag and
   by comparing against the pre-save value stored in the instance to
   avoid sending duplicate emails on subsequent saves of already-approved
   articles (e.g. minor edits by an editor).
"""

import logging

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Article, CustomUser, Newsletter, Role

logger = logging.getLogger(__name__)

# Module-level set tracking article PKs that were already approved BEFORE
# the current save. Populated by the pre_save signal and consumed by
# post_save to detect first-time approval transitions.
# Using a set is O(1) for both add and discard operations.
_already_approved_pks = set()


# ---------------------------------------------------------------------------
# Helper: build Permission querysets for a given model
# ---------------------------------------------------------------------------


def _get_article_permissions(codenames):
    """
    Return Permission queryset for the Article model filtered by codenames.

    Args:
        codenames: Iterable of permission codenames, e.g. ['view_article'].

    Returns:
        A Permission queryset for Article content-type permissions.
    """
    article_content_type = ContentType.objects.get_for_model(Article)
    return Permission.objects.filter(
        content_type=article_content_type,
        codename__in=codenames,
    )


def _get_newsletter_permissions(codenames):
    """
    Return Permission queryset for the Newsletter model filtered by codenames.

    Args:
        codenames: Iterable of permission codenames, e.g. ['view_newsletter'].

    Returns:
        A Permission queryset for Newsletter content-type permissions.
    """
    newsletter_content_type = ContentType.objects.get_for_model(Newsletter)
    return Permission.objects.filter(
        content_type=newsletter_content_type,
        codename__in=codenames,
    )


def setup_groups():
    """
    Idempotently create the three role-based Groups and assign permissions.

    This function is safe to call multiple times; get_or_create ensures
    no duplicate groups are created. It is called:

    - By the management command ``setup_news_groups``.
    - By the assign_user_group signal on every user save (via try/except).
    - By register_view after a new user is created.

    Permission layout:

    - Reader: view only (no content creation or modification)
    - Editor: view, change, delete (approve workflow, no article creation)
    - Journalist: view, add, change, delete (full CRUD on own content)
    """
    # -- Reader group: view-only permissions ---------------------------------
    reader_group, _ = Group.objects.get_or_create(name='Reader')
    reader_permissions = (
        list(_get_article_permissions(['view_article']))
        + list(_get_newsletter_permissions(['view_newsletter']))
    )
    reader_group.permissions.set(reader_permissions)

    # -- Editor group: view + change + delete (no add_article) ---------------
    editor_group, _ = Group.objects.get_or_create(name='Editor')
    editor_permissions = (
        list(_get_article_permissions(
            ['view_article', 'change_article', 'delete_article']
        ))
        + list(_get_newsletter_permissions(
            ['view_newsletter', 'change_newsletter', 'delete_newsletter']
        ))
    )
    editor_group.permissions.set(editor_permissions)

    # -- Journalist group: full CRUD on articles and newsletters -------------
    journalist_group, _ = Group.objects.get_or_create(name='Journalist')
    journalist_permissions = (
        list(_get_article_permissions(
            ['view_article', 'add_article',
             'change_article', 'delete_article']
        ))
        + list(_get_newsletter_permissions(
            ['view_newsletter', 'add_newsletter',
             'change_newsletter', 'delete_newsletter']
        ))
    )
    journalist_group.permissions.set(journalist_permissions)


# ---------------------------------------------------------------------------
# Signal 1: Track pre-save approval state (REQ 1 - logical error fix)
# ---------------------------------------------------------------------------


@receiver(pre_save, sender=Article)
def track_pre_save_approval(sender, instance, **kwargs):
    """
    Before an Article is saved, record whether it was already approved.

    This pre_save hook populates _already_approved_pks with the PK of
    any Article that is already approved in the database. The post_save
    handler uses this to detect first-time approval transitions and
    avoid firing duplicate emails on re-saves of approved articles.

    New articles (pk is None) are never in _already_approved_pks.
    """
    if instance.pk is None:
        # Brand-new article - cannot be pre-approved
        return

    try:
        # Fetch only the 'approved' field to minimise DB overhead
        current_approved = Article.objects.filter(
            pk=instance.pk
        ).values_list('approved', flat=True).first()

        if current_approved:
            # Was already approved before this save - track its PK
            _already_approved_pks.add(instance.pk)
        else:
            # Not yet approved before this save - ensure it is not tracked
            _already_approved_pks.discard(instance.pk)

    except Exception as lookup_error:
        # Non-fatal: if we cannot determine previous state, err on the
        # side of not sending emails to avoid duplicate notifications.
        logger.warning(
            "Could not determine pre-save approval for article pk=%s: %s",
            instance.pk,
            lookup_error,
        )
        _already_approved_pks.discard(instance.pk)


# ---------------------------------------------------------------------------
# Signal 2: Assign user to the correct Group after save
# ---------------------------------------------------------------------------


@receiver(post_save, sender=CustomUser)
def assign_user_group(sender, instance, created, **kwargs):
    """
    Assign the saved user to the Django auth Group matching their role.

    The user is removed from all other role groups first so that role
    changes (e.g. Reader -> Journalist) are reflected immediately.

    setup_groups() is called inside a try/except because it may fail
    during the initial database migration when content types are not
    yet available.
    """
    # Maps each role value to its corresponding group name
    role_to_group_name = {
        Role.READER: 'Reader',
        Role.JOURNALIST: 'Journalist',
        Role.EDITOR: 'Editor',
    }

    target_group_name = role_to_group_name.get(instance.role)
    if not target_group_name:
        logger.warning(
            "Unknown role '%s' for user '%s'; no group assigned.",
            instance.role,
            instance.username,
        )
        return

    # Ensure groups and permissions exist before assigning
    try:
        setup_groups()
    except Exception as setup_error:
        # setup_groups may fail during early migrations - log and return
        logger.debug("setup_groups() skipped in signal: %s", setup_error)
        return

    # Remove from all role groups then add to the correct one
    all_role_groups = Group.objects.filter(
        name__in=role_to_group_name.values()
    )
    instance.groups.remove(*all_role_groups)

    target_group = Group.objects.get(name=target_group_name)
    instance.groups.add(target_group)

    logger.info(
        "User '%s' assigned to group '%s'.",
        instance.username,
        target_group_name,
    )


# ---------------------------------------------------------------------------
# Signal 3: Handle first-time article approval
# ---------------------------------------------------------------------------


@receiver(post_save, sender=Article)
def article_approved(sender, instance, created, **kwargs):
    """
    Fire subscriber notifications only when an article is approved
    for the FIRST TIME.

    Logic:
      - If the article is not approved, do nothing.
      - If the article's PK was in _already_approved_pks (meaning it was
        already approved before this save), do nothing. This prevents
        duplicate emails from editor re-saves of published articles.
      - Otherwise (first-time approval), notify subscribers and log.

    The PK is removed from _already_approved_pks after handling so the
    set does not grow unboundedly.
    """
    if not instance.approved:
        # Article is not approved - nothing to do
        return

    if instance.pk in _already_approved_pks:
        # Article was already approved before this save - skip to avoid
        # sending duplicate emails on subsequent edits of live articles.
        _already_approved_pks.discard(instance.pk)
        logger.debug(
            "Skipping approval signal for already-approved article pk=%s.",
            instance.pk,
        )
        return

    # First-time approval: notify subscribers and log the event
    logger.info(
        "Article '%s' (pk=%s) approved for first time — notifying.",
        instance.title,
        instance.pk,
    )
    _notify_subscribers(instance)
    _post_to_approved_endpoint(instance)


# ---------------------------------------------------------------------------
# Helper: collect subscriber email addresses
# ---------------------------------------------------------------------------


def _collect_subscriber_emails(article):
    """
    Return a deduplicated list of email addresses for all users subscribed
    to either the article's author (journalist) or its publisher.

    Uses a single combined query with Q objects rather than two separate
    querysets to minimise database round-trips (REQ 4 - efficiency).

    Args:
        article: The approved Article instance.

    Returns:
        A list of non-empty email address strings.
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    User = get_user_model()

    # Build filter conditions dynamically to handle articles with no publisher
    subscription_filter = Q()

    if article.author_id:
        # Readers who follow this journalist
        subscription_filter |= Q(subscribed_journalists=article.author)

    if article.publisher_id:
        # Readers subscribed to this publisher
        subscription_filter |= Q(subscribed_publishers=article.publisher)

    if not subscription_filter:
        # Neither author nor publisher is set - no subscribers possible
        return []

    # Single query combining both subscription types with deduplication
    subscriber_emails = list(
        User.objects.filter(subscription_filter)
        .exclude(email='')
        .values_list('email', flat=True)
        .distinct()
    )

    return subscriber_emails


# ---------------------------------------------------------------------------
# Helper: send email notifications to subscribers
# ---------------------------------------------------------------------------


def _notify_subscribers(article):
    """
    Send an email notification to every subscriber of the approved article.

    Constructs a plain-text email containing the article title and author,
    then sends it to the collected subscriber email list.
    If no subscribers exist, logs the fact and returns without sending.
    Any send_mail exception is caught and logged so that an email failure
    does not crash the approval workflow.
    """
    recipient_emails = _collect_subscriber_emails(article)

    if not recipient_emails:
        logger.info(
            "No subscribers to notify for article '%s' (pk=%s).",
            article.title,
            article.pk,
        )
        return

    # Build a human-readable author display name
    author_display_name = (
        article.author.get_full_name() or article.author.username
    )

    email_subject = f"New Article Published: {article.title}"
    email_body = (
        f"A new article has been published:\n\n"
        f"Title  : {article.title}\n"
        f"Author : {author_display_name}\n\n"
        f"Log in to read the full article."
    )

    try:
        send_mail(
            subject=email_subject,
            message=email_body,
            from_email=None,  # uses DEFAULT_FROM_EMAIL from settings.py
            recipient_list=recipient_emails,
            fail_silently=False,
        )
        logger.info(
            "Approval email sent for article '%s' to %d subscriber(s).",
            article.title,
            len(recipient_emails),
        )
    except Exception as email_error:
        # Log the error but do not re-raise - a failed email must not
        # prevent the article from being marked as approved in the DB.
        logger.error(
            "Failed to send approval email for article '%s' (pk=%s): %s",
            article.title,
            article.pk,
            email_error,
        )


# ---------------------------------------------------------------------------
# Helper: POST approved article details to internal API endpoint
# ---------------------------------------------------------------------------


def _post_to_approved_endpoint(article):
    """
    POST the approved article's details to /api/approved/ for logging.

    This simulates notifying an external service when an article goes live.
    The call is made with a short timeout and all exceptions are caught so
    that a network failure does not crash the approval workflow.

    Note: In production this should be moved to a background task (e.g.
    Celery) to avoid blocking the request/response cycle. The synchronous
    call here is acceptable for the development/demo context of this project.
    """
    try:
        import requests  # imported here to avoid circular import issues

        # Determine publisher name safely (publisher is nullable)
        publisher_name = (
            article.publisher.name if article.publisher else None
        )

        # Build the payload matching ArticleApprovalSerializer fields
        approval_payload = {
            'article_id': article.pk,
            'title': article.title,
            'author': article.author.username,
            'publisher': publisher_name,
            'approved': article.approved,
        }

        response = requests.post(
            'http://127.0.0.1:8000/api/approved/',
            json=approval_payload,
            timeout=5,  # seconds - prevent hanging on slow/unavailable server
        )
        response.raise_for_status()

        logger.info(
            "Successfully POSTed article '%s' (pk=%s) to /api/approved/.",
            article.title,
            article.pk,
        )

    except ImportError:
        logger.warning(
            "'requests' library not installed; skipping /api/approved/ POST."
        )
    except Exception as request_error:
        # Log but do not re-raise - a failed webhook must not prevent
        # the article approval from completing successfully.
        logger.error(
            "Failed to POST article '%s' (pk=%s) to /api/approved/: %s",
            article.title,
            article.pk,
            request_error,
        )
