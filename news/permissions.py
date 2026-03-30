"""
permissions.py - Custom DRF permission classes.

Enforces role-based access control at the API layer, complementing
the Django auth Group permissions assigned in signals.py.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Role


class IsJournalist(BasePermission):
    """Allow access only to users with the Journalist role."""

    message = "Only journalists can perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.JOURNALIST
        )


class IsEditor(BasePermission):
    """Allow access only to users with the Editor role."""

    message = "Only editors can perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.EDITOR
        )


class IsJournalistOrEditor(BasePermission):
    """Allow access to journalists and editors."""

    message = "Only journalists or editors can perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (Role.JOURNALIST, Role.EDITOR)
        )


class IsOwnerOrEditor(BasePermission):
    """
    Object-level permission:
      - Editors can access any object.
      - Journalists can only access objects they authored.
    """

    message = "You do not have permission to modify this object."

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == Role.EDITOR:
            return True

        # Journalists can only edit their own articles/newsletters
        if hasattr(obj, 'author'):
            return obj.author == request.user

        return False


class ReadOnly(BasePermission):
    """Permits GET, HEAD, and OPTIONS requests only."""

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
