"""
serializers.py - DRF serializers for the News application.

Serializers
-----------
PublisherSerializer        - full publisher details
UserSerializer             - safe read-only user representation
ArticleSerializer          - article with nested author/publisher info
NewsletterSerializer       - newsletter with nested articles
ArticleApprovalSerializer  - minimal write serializer for approval
RegisterSerializer         - new user registration
"""

from rest_framework import serializers

from .models import Article, CustomUser, Newsletter, Publisher


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------


class PublisherSerializer(serializers.ModelSerializer):
    """Serialises a Publisher for list and detail views."""

    class Meta:
        model = Publisher
        fields = ['id', 'name', 'description', 'website', 'created_at']
        read_only_fields = ['id', 'created_at']


# ---------------------------------------------------------------------------
# User (read-only, safe subset of fields)
# ---------------------------------------------------------------------------


class UserSerializer(serializers.ModelSerializer):
    """
    Read-only serialiser exposing non-sensitive user information.
    Used for nested representations inside Article and Newsletter.
    """

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email', 'role'
        ]
        read_only_fields = [
            'id', 'username', 'first_name', 'last_name', 'email', 'role'
        ]


# ---------------------------------------------------------------------------
# Article
# ---------------------------------------------------------------------------


class ArticleSerializer(serializers.ModelSerializer):
    """
    Full Article serialiser.
    - Read:  returns nested author and publisher objects.
    - Write: accepts author_id and publisher_id as plain integer IDs.
    """

    # Nested read representations
    author_detail = UserSerializer(source='author', read_only=True)
    publisher_detail = PublisherSerializer(
        source='publisher', read_only=True
    )

    class Meta:
        model = Article
        fields = [
            'id',
            'title',
            'content',
            'created_at',
            'updated_at',
            'approved',
            'author',           # write (PK)
            'author_detail',    # read (nested)
            'publisher',        # write (PK, nullable)
            'publisher_detail',  # read (nested)
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'approved',
            'author_detail', 'publisher_detail',
        ]
        extra_kwargs = {
            'author': {'write_only': True},
            'publisher': {'write_only': True, 'required': False},
        }

    def validate_author(self, user):
        """Only journalists may author articles."""
        from .models import Role
        if user.role != Role.JOURNALIST:
            raise serializers.ValidationError(
                "Only journalists can author articles."
            )
        return user


# ---------------------------------------------------------------------------
# Newsletter
# ---------------------------------------------------------------------------


class NewsletterSerializer(serializers.ModelSerializer):
    """
    Newsletter serialiser.
    - `articles` accepts a list of Article PKs on write.
    - `articles_detail` returns nested article objects on read.
    """

    articles_detail = ArticleSerializer(
        source='articles', many=True, read_only=True
    )
    author_detail = UserSerializer(source='author', read_only=True)

    class Meta:
        model = Newsletter
        fields = [
            'id',
            'title',
            'description',
            'created_at',
            'updated_at',
            'author',            # write (PK)
            'author_detail',     # read (nested)
            'articles',          # write (list of PKs)
            'articles_detail',   # read (nested)
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'author_detail', 'articles_detail',
        ]
        extra_kwargs = {
            'author': {'write_only': True},
            'articles': {'write_only': True, 'required': False},
        }


# ---------------------------------------------------------------------------
# Article Approval (internal /api/approved/ endpoint)
# ---------------------------------------------------------------------------


class ArticleApprovalSerializer(serializers.Serializer):
    """
    Serialiser for the internal /api/approved/ POST endpoint.
    Validates the payload sent by the post_save signal.
    """

    article_id = serializers.IntegerField()
    title = serializers.CharField(max_length=255)
    author = serializers.CharField(max_length=150)
    publisher = serializers.CharField(
        max_length=255, allow_null=True, required=False
    )
    approved = serializers.BooleanField()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class RegisterSerializer(serializers.ModelSerializer):
    """Serialiser used for new user registration via the API."""

    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(
        write_only=True, label='Confirm password'
    )

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'role', 'publisher', 'password', 'password2',
        ]
        extra_kwargs = {
            'publisher': {'required': False},
        }

    def validate(self, data):
        """Ensure the two password fields match."""
        if data['password'] != data.pop('password2'):
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def create(self, validated_data):
        """Create a new user with a hashed password."""
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        return user
