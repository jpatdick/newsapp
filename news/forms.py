"""
forms.py - Django forms for the News application.

Forms
-----
RegisterForm   - New user registration (with role selection).
ArticleForm    - Create or edit an article.
NewsletterForm - Create or edit a newsletter.
PublisherForm  - Create or edit a publisher (editors only).

Defensive coding notes
----------------------
- clean_email() normalises email to lowercase AND checks for duplicates,
  preventing case-insensitive duplicate accounts (e.g. A@b.com vs a@b.com).
- clean_title() strips whitespace and enforces a minimum meaningful length
  beyond what the database max_length constraint alone would catch.
- NewsletterForm.__init__ restricts the articles queryset to approved-only,
  preventing unapproved drafts from being included in published newsletters.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Article, CustomUser, Newsletter, Publisher, Role


# ---------------------------------------------------------------------------
# User registration
# ---------------------------------------------------------------------------


class RegisterForm(UserCreationForm):
    """
    Extended registration form capturing name, email, and role.

    Adds first_name, last_name, email, and role to the standard
    Django UserCreationForm (which provides username, password1, password2).
    """

    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'First name'}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Last name'}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'Email address'}),
    )
    role = forms.ChoiceField(
        choices=Role.choices,
        initial=Role.READER,
        help_text=(
            "Readers can view content; journalists can create it; "
            "editors approve it."
        ),
    )

    class Meta:
        model = CustomUser
        fields = [
            'username', 'first_name', 'last_name', 'email',
            'role', 'password1', 'password2',
        ]

    def clean_email(self):
        """
        Validate and normalise the email address.

        Steps:
          1. Normalise to lowercase so that 'A@b.com' and 'a@b.com'
             are treated as the same address (case-insensitive dedup).
          2. Check the database for an existing account with that email.

        Raises ValidationError if the email is already registered.
        """
        # Normalise to lowercase for consistent, case-insensitive storage
        normalised_email = self.cleaned_data.get('email', '').lower()

        if CustomUser.objects.filter(email=normalised_email).exists():
            raise forms.ValidationError(
                "A user with this email already exists."
            )

        return normalised_email


# ---------------------------------------------------------------------------
# Article
# ---------------------------------------------------------------------------


class ArticleForm(forms.ModelForm):
    """
    Form for creating and editing articles.

    Validation:
      - Title must not be blank or whitespace-only.
      - Title must be at least 5 characters after stripping whitespace,
        preventing trivially short or meaningless titles.
    """

    class Meta:
        model = Article
        fields = ['title', 'content', 'publisher']
        widgets = {
            'title': forms.TextInput(
                attrs={'placeholder': 'Article title'}
            ),
            'content': forms.Textarea(
                attrs={
                    'rows': 12,
                    'placeholder': 'Write your article here...',
                }
            ),
        }
        help_texts = {
            'publisher': (
                "Leave blank to publish as an independent article."
            ),
        }

    def clean_title(self):
        """
        Validate the article title.

        Strips leading/trailing whitespace, then checks:
          - The title is not empty after stripping.
          - The title is at least 5 characters long (avoids trivial titles
            like 'A' or '???' that pass the database max_length check).
        """
        title = self.cleaned_data.get('title', '').strip()

        if not title:
            raise forms.ValidationError(
                "Please enter a valid article title."
            )

        # Enforce a minimum meaningful title length
        if len(title) < 5:
            raise forms.ValidationError(
                "The article title must be at least 5 characters long."
            )

        return title


# ---------------------------------------------------------------------------
# Newsletter
# ---------------------------------------------------------------------------


class NewsletterForm(forms.ModelForm):
    """
    Form for creating and editing newsletters.

    The articles field is restricted to approved articles only - unapproved
    drafts must not appear in published newsletters seen by readers.
    """

    class Meta:
        model = Newsletter
        fields = ['title', 'description', 'articles']
        widgets = {
            'title': forms.TextInput(
                attrs={'placeholder': 'Newsletter title'}
            ),
            'description': forms.Textarea(
                attrs={
                    'rows': 5,
                    'placeholder': 'Describe this newsletter...',
                }
            ),
            # Checkboxes allow selecting multiple articles at once
            'articles': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Restrict the articles queryset to approved (published) articles only.
        # This prevents journalists from accidentally including draft content
        # in a newsletter that readers will see.
        self.fields['articles'].queryset = (
            Article.objects.filter(approved=True)
            .select_related('author')
        )


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------


class PublisherForm(forms.ModelForm):
    """
    Form for editors to create and manage publisher organisations.

    All three fields are optional at the model level except name,
    which must be unique - the model enforces uniqueness at the DB layer
    and Django surfaces a validation error if a duplicate name is submitted.
    """

    class Meta:
        model = Publisher
        fields = ['name', 'description', 'website']
        widgets = {
            'name': forms.TextInput(
                attrs={'placeholder': 'Publisher name'}
            ),
            'description': forms.Textarea(
                attrs={
                    'rows': 4,
                    'placeholder': 'Brief description of this publisher...',
                }
            ),
            'website': forms.URLInput(
                attrs={'placeholder': 'https://example.com'}
            ),
        }
