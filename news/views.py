"""
views.py - Web UI views for the News application.

Provides template-based views for:
  - User registration and login/logout
  - Article browsing, detail, creation, and editing
  - Editor article-approval dashboard
  - Newsletter browsing, creation, editing, and deletion
  - Publisher listing, creation, and editing
  - Subscription toggling (readers only)

Defensive coding conventions used throughout
--------------------------------------------
- All user input is validated through Django forms before saving.
- Role guards use @user_passes_test to reject unauthorised access early.
- Ownership checks are centralised in helpers to avoid duplication.
- The ?next= redirect parameter is validated against a safe-URL whitelist
  to prevent open-redirect attacks.
- All DB lookups use get_object_or_404 to handle missing records cleanly.
"""

from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ArticleForm, NewsletterForm, PublisherForm, RegisterForm
from .models import Article, CustomUser, Newsletter, Publisher, Role
from .signals import setup_groups


# ---------------------------------------------------------------------------
# Role-based access helpers
# ---------------------------------------------------------------------------


def _is_editor(user):
    """Return True if the authenticated user has the Editor role."""
    return user.is_authenticated and user.role == Role.EDITOR


def _is_journalist(user):
    """Return True if the authenticated user has the Journalist role."""
    return user.is_authenticated and user.role == Role.JOURNALIST


def _is_journalist_or_editor(user):
    """Return True if the user is a journalist or editor."""
    return (
        user.is_authenticated
        and user.role in (Role.JOURNALIST, Role.EDITOR)
    )


# ---------------------------------------------------------------------------
# Ownership / access guard helpers  (REQ 3 - modularity)
# ---------------------------------------------------------------------------


def _journalist_owns_article(user, article):
    """
    Return True if the given journalist-role user authored the article.
    Extracted so the ownership rule is defined in exactly one place.
    """
    return article.author == user


def _journalist_owns_newsletter(user, newsletter):
    """
    Return True if the given journalist-role user authored the newsletter.
    Extracted so the ownership rule is defined in exactly one place.
    """
    return newsletter.author == user


def _safe_redirect_url(next_url, fallback='articles'):
    """
    Validate the ?next= redirect parameter to prevent open-redirect attacks.

    Only relative paths (no scheme, no netloc) are accepted as safe.
    Returns the named fallback URL when next_url is absent or unsafe.

    Args:
        next_url: The raw string from request.GET.get('next').
        fallback: Named URL to redirect to when next_url is unsafe.

    Returns:
        A safe URL string or named URL to pass to redirect().
    """
    if not next_url:
        return fallback

    parsed = urlparse(next_url)

    # Reject absolute URLs - scheme or netloc indicates an off-site target
    if parsed.scheme or parsed.netloc:
        return fallback

    return next_url


def _check_journalist_article_access(request, article):
    """
    Validate that a journalist may edit the given article.

    Rules enforced:
      1. The journalist must be the article's author.
      2. The article must not yet have been approved (published).

    Returns an HttpResponse redirect if access is denied, or None to
    signal that the caller should proceed. Centralising these two rules
    here removes duplicated logic and makes each rule independently
    testable.
    """
    # Rule 1: ownership check
    if not _journalist_owns_article(request.user, article):
        messages.error(request, "You can only edit your own articles.")
        return redirect('articles')

    # Rule 2: approved articles are locked against post-publication edits
    if article.approved:
        messages.error(
            request,
            "This article has already been published and cannot be edited.",
        )
        return redirect('articles')

    return None  # access granted; caller should proceed


def _check_journalist_newsletter_access(request, newsletter, action):
    """
    Validate that a journalist may modify (edit or delete) the newsletter.

    Args:
        request:    The current HTTP request (used to access request.user).
        newsletter: The Newsletter instance being modified.
        action:     'edit' or 'delete' - included in the denial message.

    Returns an HttpResponse redirect if access is denied, or None to
    signal that the caller should proceed. Extracted from both
    edit_newsletter_view and delete_newsletter_view to eliminate the
    duplicated ownership check that previously existed in both places.
    """
    if not _journalist_owns_newsletter(request.user, newsletter):
        messages.error(
            request,
            f"You can only {action} your own newsletters.",
        )
        return redirect('newsletter_list')

    return None  # access granted


# ---------------------------------------------------------------------------
# Authentication views
# ---------------------------------------------------------------------------


def register_view(request):
    """
    Display and process the user registration form.

    On success the user is logged in and redirected to the article list.
    setup_groups() is wrapped in a try/except so a group-creation failure
    (e.g. during early migrations in testing) does not prevent registration.
    """
    # Authenticated users have no reason to see the registration page
    if request.user.is_authenticated:
        return redirect('articles')

    form = RegisterForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        new_user = form.save()

        # Ensure role groups exist; non-fatal if they cannot be created now
        # because the post_save signal will retry assignment later.
        try:
            setup_groups()
        except Exception as group_error:
            import logging
            logging.getLogger(__name__).warning(
                "setup_groups() failed after registration for '%s': %s",
                new_user.username,
                group_error,
            )

        login(request, new_user)
        messages.success(
            request,
            f"Welcome, {new_user.username}! Your account has been created.",
        )
        return redirect('articles')

    return render(request, 'news/register.html', {'form': form})


def login_view(request):
    """
    Display and process the login form.

    Input validation:
      - Both username and password must be non-empty strings.
      - The ?next= parameter is sanitised via _safe_redirect_url() to
        prevent open-redirect attacks.
    """
    # Authenticated users are redirected away immediately
    if request.user.is_authenticated:
        return redirect('articles')

    error_message = None

    if request.method == 'POST':
        # Strip whitespace from username; leave password exactly as typed
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Defensive: reject the attempt before hitting the DB if fields empty
        if not username or not password:
            error_message = "Please enter both your username and password."
        else:
            authenticated_user = authenticate(
                request, username=username, password=password
            )

            if authenticated_user is not None:
                login(request, authenticated_user)

                # Validate ?next= before redirecting to prevent open redirects
                raw_next = request.GET.get('next', '')
                safe_next = _safe_redirect_url(
                    raw_next, fallback='articles'
                )
                return redirect(safe_next)
            else:
                # Vague by design - do not reveal which field failed
                error_message = "Invalid username or password."

    return render(request, 'news/login.html', {'error': error_message})


@login_required
def logout_view(request):
    """Log out the current user and redirect to the login page."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')


# ---------------------------------------------------------------------------
# Home / article list
# ---------------------------------------------------------------------------


@login_required
def home_view(request):
    """
    Landing page displaying a list of articles.

    - Readers see only approved (published) articles.
    - Journalists and editors see all articles including pending drafts.
    - Results are ordered newest-first in both cases.
    - select_related() prefetches the author and publisher in the same
      query to avoid N+1 database hits in the template loop.
    """
    user = request.user

    if user.role in (Role.JOURNALIST, Role.EDITOR):
        # Staff can see all articles regardless of approval status
        articles = (
            Article.objects.all()
            .select_related('author', 'publisher')
            .order_by('-created_at')
        )
    else:
        # Readers only see published content
        articles = (
            Article.objects.filter(approved=True)
            .select_related('author', 'publisher')
            .order_by('-created_at')
        )

    return render(request, 'news/home.html', {'articles': articles})


# ---------------------------------------------------------------------------
# Article detail
# ---------------------------------------------------------------------------


@login_required
def article_detail_view(request, pk):
    """
    Display a single article by primary key.

    Readers who attempt to access an unapproved article receive an
    informative error message and are redirected rather than seeing
    a misleading 404 or a raw permission error.
    """
    article = get_object_or_404(Article, pk=pk)

    # Readers must not see content that has not yet been published
    if request.user.role == Role.READER and not article.approved:
        messages.error(request, "This article is not yet published.")
        return redirect('articles')

    return render(
        request, 'news/article_detail.html', {'article': article}
    )


# ---------------------------------------------------------------------------
# Editor approval dashboard
# ---------------------------------------------------------------------------


@login_required
@user_passes_test(_is_editor, login_url='/login/')
def editor_dashboard_view(request):
    """
    Editor-only dashboard listing articles that are pending approval.

    Articles are ordered oldest-first (ascending created_at) so that the
    submissions that have been waiting longest appear at the top.
    """
    pending_articles = (
        Article.objects.filter(approved=False)
        .select_related('author', 'publisher')
        .order_by('created_at')  # oldest-pending first
    )
    return render(
        request,
        'news/editor_dashboard.html',
        {'articles': pending_articles},
    )


@login_required
@user_passes_test(_is_editor, login_url='/login/')
def approve_article_view(request, pk):
    """
    POST endpoint allowing an editor to approve a pending article.

    Saving the article with approved=True triggers the post_save signal
    in signals.py, which emails subscribers and notifies the API.
    A warning is displayed on double-approval attempts (e.g. browser
    back-button) to prevent duplicate signal fires.
    """
    article = get_object_or_404(Article, pk=pk)

    if request.method == 'POST':
        if article.approved:
            # Guard against duplicate approvals from repeated POST requests
            messages.warning(
                request, f"'{article.title}' is already approved."
            )
        else:
            article.approved = True
            article.save()  # fires signals.py -> email + internal webhook
            messages.success(
                request,
                f"'{article.title}' has been approved and published.",
            )
        return redirect('editor_dashboard')

    # GET: display a confirmation page before committing the approval
    return render(
        request, 'news/approve_confirm.html', {'article': article}
    )


# ---------------------------------------------------------------------------
# Journalist: create and edit articles
# ---------------------------------------------------------------------------


@login_required
@user_passes_test(_is_journalist, login_url='/login/')
def create_article_view(request):
    """
    Allow a journalist to submit a new article for editor review.

    The author field is always set to the current user regardless of
    any value that might be present in the POST data, enforcing that
    journalists can only author articles under their own name.
    """
    form = ArticleForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        new_article = form.save(commit=False)
        new_article.author = request.user  # enforce ownership
        new_article.save()
        messages.success(
            request,
            f"Article '{new_article.title}' submitted for review.",
        )
        return redirect('articles')

    return render(
        request,
        'news/article_form.html',
        {'form': form, 'action': 'Create'},
    )


@login_required
@user_passes_test(_is_journalist_or_editor, login_url='/login/')
def edit_article_view(request, pk):
    """
    Allow a journalist (owner) or editor to edit an existing article.

    Journalist-specific access restrictions are validated through
    ``_check_journalist_article_access()``, which checks:

    - The journalist must be the article's author.
    - The article must not yet be approved (published).

    These checks are centralised in the helper to keep this view concise.
    """
    article = get_object_or_404(Article, pk=pk)

    # Journalists have additional ownership and approval-status restrictions
    if request.user.role == Role.JOURNALIST:
        denial_response = _check_journalist_article_access(
            request, article
        )
        if denial_response:
            return denial_response  # access denied; helper set the message

    form = ArticleForm(request.POST or None, instance=article)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(
            request, f"Article '{article.title}' updated."
        )
        return redirect('article_detail', pk=article.pk)

    return render(
        request,
        'news/article_form.html',
        {'form': form, 'action': 'Edit'},
    )


# ---------------------------------------------------------------------------
# Newsletters - list and detail
# ---------------------------------------------------------------------------


@login_required
def newsletter_list_view(request):
    """
    Display all newsletters to any authenticated user.
    prefetch_related() avoids N+1 queries when the template lists articles
    within each newsletter.
    """
    newsletters = (
        Newsletter.objects.all()
        .select_related('author')
        .prefetch_related('articles')
    )
    return render(
        request,
        'news/newsletter_list.html',
        {'newsletters': newsletters},
    )


@login_required
def newsletter_detail_view(request, pk):
    """Display a single newsletter with its associated articles."""
    newsletter = get_object_or_404(Newsletter, pk=pk)
    return render(
        request,
        'news/newsletter_detail.html',
        {'newsletter': newsletter},
    )


# ---------------------------------------------------------------------------
# Newsletters - create, edit, delete
# ---------------------------------------------------------------------------


@login_required
@user_passes_test(_is_journalist_or_editor, login_url='/login/')
def create_newsletter_view(request):
    """
    Allow journalists and editors to create a newsletter.

    The author is always forced to the current user.
    form.save_m2m() must be called explicitly after save(commit=False)
    to persist the ManyToMany 'articles' relationship.
    """
    form = NewsletterForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        newsletter = form.save(commit=False)
        newsletter.author = request.user  # enforce ownership
        newsletter.save()
        form.save_m2m()  # persist the M2M articles relationship
        messages.success(
            request, f"Newsletter '{newsletter.title}' created."
        )
        return redirect('newsletter_list')

    return render(
        request,
        'news/newsletter_form.html',
        {'form': form, 'action': 'Create'},
    )


@login_required
@user_passes_test(_is_journalist_or_editor, login_url='/login/')
def edit_newsletter_view(request, pk):
    """
    Allow a journalist (owner) or editor to edit a newsletter.

    Journalist ownership is validated through
    _check_journalist_newsletter_access(),
    keeping the ownership rule in one place and this view concise.
    """
    newsletter = get_object_or_404(Newsletter, pk=pk)

    # Journalists may only edit newsletters they own
    if request.user.role == Role.JOURNALIST:
        denial_response = _check_journalist_newsletter_access(
            request, newsletter, action='edit'
        )
        if denial_response:
            return denial_response

    form = NewsletterForm(request.POST or None, instance=newsletter)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(
            request, f"Newsletter '{newsletter.title}' updated."
        )
        return redirect('newsletter_detail', pk=newsletter.pk)

    return render(
        request,
        'news/newsletter_form.html',
        {'form': form, 'action': 'Edit'},
    )


@login_required
@user_passes_test(_is_journalist_or_editor, login_url='/login/')
def delete_newsletter_view(request, pk):
    """
    Allow a journalist (owner) or editor to delete a newsletter.

    GET  - Renders a confirmation page before the irreversible delete.
    POST - Performs the deletion and redirects with a success message.

    The newsletter title is captured before deletion so it can still
    be referenced in the success message after the object is gone.
    """
    newsletter = get_object_or_404(Newsletter, pk=pk)

    # Journalists may only delete newsletters they own
    if request.user.role == Role.JOURNALIST:
        denial_response = _check_journalist_newsletter_access(
            request, newsletter, action='delete'
        )
        if denial_response:
            return denial_response

    if request.method == 'POST':
        # Capture title before the object is removed from the database
        deleted_title = newsletter.title
        newsletter.delete()
        messages.success(
            request, f"Newsletter '{deleted_title}' deleted."
        )
        return redirect('newsletter_list')

    # GET: ask the user to confirm before deleting
    return render(
        request,
        'news/newsletter_confirm_delete.html',
        {'newsletter': newsletter},
    )


# ---------------------------------------------------------------------------
# Publisher list and reader subscriptions
# ---------------------------------------------------------------------------


@login_required
def publisher_list_view(request):
    """
    Display all publishers alphabetically.
    Readers can subscribe or unsubscribe directly from this view.
    """
    publishers = Publisher.objects.all().order_by('name')
    return render(
        request,
        'news/publisher_list.html',
        {'publishers': publishers},
    )


@login_required
def subscribe_publisher_view(request, pk):
    """
    Allow a reader to toggle their subscription to a publisher.

    Non-reader roles receive an informative error rather than a generic
    permission denial, making the restriction clear to the user.
    The subscription state is toggled: subscribing again unsubscribes.
    """
    if request.user.role != Role.READER:
        messages.error(
            request, "Only readers can subscribe to publishers."
        )
        return redirect('publisher_list')

    publisher = get_object_or_404(Publisher, pk=pk)

    # Check current subscription state before toggling
    already_subscribed = request.user.subscribed_publishers.filter(
        pk=publisher.pk
    ).exists()

    if already_subscribed:
        request.user.subscribed_publishers.remove(publisher)
        messages.info(request, f"Unsubscribed from {publisher.name}.")
    else:
        request.user.subscribed_publishers.add(publisher)
        messages.success(request, f"Subscribed to {publisher.name}.")

    return redirect('publisher_list')


@login_required
def subscribe_journalist_view(request, pk):
    """
    Allow a reader to toggle their subscription (follow) to a journalist.

    Non-reader roles receive an informative error.
    get_object_or_404 restricts the lookup to users with a JOURNALIST role,
    preventing readers from following editors or other readers.
    """
    if request.user.role != Role.READER:
        messages.error(request, "Only readers can follow journalists.")
        return redirect('articles')

    # Restrict lookup to journalist-role users only for safety
    journalist = get_object_or_404(
        CustomUser, pk=pk, role=Role.JOURNALIST
    )

    # Check current follow state before toggling
    already_following = request.user.subscribed_journalists.filter(
        pk=journalist.pk
    ).exists()

    if already_following:
        request.user.subscribed_journalists.remove(journalist)
        messages.info(request, f"Unfollowed {journalist.username}.")
    else:
        request.user.subscribed_journalists.add(journalist)
        messages.success(
            request, f"Now following {journalist.username}."
        )

    return redirect('articles')


# ---------------------------------------------------------------------------
# Editor: publisher management
# ---------------------------------------------------------------------------


@login_required
@user_passes_test(_is_editor, login_url='/login/')
def create_publisher_view(request):
    """Allow editors to create a new publisher organisation."""
    form = PublisherForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        publisher = form.save()
        messages.success(
            request, f"Publisher '{publisher.name}' created."
        )
        return redirect('publisher_list')

    return render(
        request,
        'news/publisher_form.html',
        {'form': form, 'action': 'Create'},
    )


@login_required
@user_passes_test(_is_editor, login_url='/login/')
def edit_publisher_view(request, pk):
    """Allow editors to update the details of an existing publisher."""
    publisher = get_object_or_404(Publisher, pk=pk)
    form = PublisherForm(request.POST or None, instance=publisher)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(
            request, f"Publisher '{publisher.name}' updated."
        )
        return redirect('publisher_list')

    return render(
        request,
        'news/publisher_form.html',
        {'form': form, 'action': 'Edit'},
    )
