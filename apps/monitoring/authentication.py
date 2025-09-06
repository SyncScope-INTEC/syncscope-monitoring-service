"""
JWT Authentication for monitoring service.
"""

import logging

from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .auth_utils import ServiceAuthManager

logger = logging.getLogger(__name__)


class JWTAuthentication(BaseAuthentication):
    """
    JWT token authentication for monitoring service.
    """

    def authenticate(self, request):
        """
        Authenticate the request and return a two-tuple of (user, token).
        """
        auth_header = request.META.get("HTTP_AUTHORIZATION")

        if not auth_header:
            return None

        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]

        try:
            auth_manager = ServiceAuthManager()
            user_data = auth_manager.verify_user_token(token)

            if not user_data:
                raise AuthenticationFailed("Invalid token")

            # Create a simple user object with the data from token
            user = MonitoringUser(user_data)

            return (user, token)

        except Exception as e:
            logger.error(f"JWT Authentication failed: {e}")
            raise AuthenticationFailed("Token verification failed")

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response.
        """
        return "Bearer"


class MonitoringUser:
    """
    Simple user class for monitoring service authentication.
    """

    def __init__(self, user_data):
        self.id = user_data.get("user_id")
        self.pk = user_data.get("user_id")  # Add pk for django-ratelimit compatibility
        self.user_id = user_data.get("user_id")
        self.email = user_data.get("email", "")
        self.username = user_data.get("username", "")
        self.is_authenticated = True
        self.is_anonymous = False
        self.is_staff = user_data.get("is_staff", False)
        self.is_superuser = user_data.get("is_superuser", False)
        self._user_data = user_data

    def __str__(self):
        return f"MonitoringUser({self.user_id})"

    def has_perm(self, perm, obj=None):
        """Check if user has permission."""
        return self.is_staff or self.is_superuser

    def has_perms(self, perm_list, obj=None):
        """Check if user has multiple permissions."""
        return all(self.has_perm(perm, obj) for perm in perm_list)

    def has_module_perms(self, package_name):
        """Check if user has permissions for a module."""
        return self.is_staff or self.is_superuser

    def get_user_data(self):
        """Get original user data from token."""
        return self._user_data
