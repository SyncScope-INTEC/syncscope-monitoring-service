"""
Database authentication backend that queries the auth schema directly.
"""

import logging

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from django.core.cache import cache

from .auth_models import AuthUser

logger = logging.getLogger(__name__)


class SharedDatabaseAuthBackend(BaseBackend):
    """
    Authentication backend that queries the auth.users table directly.
    Since both services share the same database, this is more efficient
    than making API calls to the auth service.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user by querying the auth.users table directly.
        """
        logger.info(f"SharedDatabaseAuthBackend: Attempting authentication for user: {username}")

        if username is None or password is None:
            logger.warning("SharedDatabaseAuthBackend: Username or password is None")
            return None

        try:
            # Query the auth.users table directly
            auth_user = AuthUser.objects.get(email=username)
            logger.info(f"SharedDatabaseAuthBackend: Found auth user: {auth_user.email}")

            # Check password
            if auth_user.check_password(password):
                logger.info(f"SharedDatabaseAuthBackend: Password check successful for: {username}")

                # Check if user has admin privileges
                if auth_user.is_active and (auth_user.is_staff or auth_user.is_superuser):
                    logger.info(f"SharedDatabaseAuthBackend: User {username} has admin privileges")

                    # Create or update local Django user for admin interface
                    user = self._get_or_create_local_user(auth_user)
                    logger.info(f"SharedDatabaseAuthBackend: Created/updated local user: {user}")
                    return user
                else:
                    logger.warning(f"SharedDatabaseAuthBackend: User {username} does not have admin privileges")
            else:
                logger.warning(f"SharedDatabaseAuthBackend: Password check failed for: {username}")

        except AuthUser.DoesNotExist:
            logger.warning(f"SharedDatabaseAuthBackend: User {username} not found in auth.users")
        except Exception as e:
            logger.error(f"SharedDatabaseAuthBackend: Error during authentication: {str(e)}", exc_info=True)

        return None

    def get_user(self, user_id):
        """
        Get user by ID for session management.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def _get_or_create_local_user(self, auth_user):
        """
        Create or update a local Django user for admin interface.
        """
        try:
            # Create or update local user
            user, created = User.objects.get_or_create(
                username=auth_user.email,
                defaults={
                    "email": auth_user.email,
                    "first_name": auth_user.first_name,
                    "last_name": auth_user.last_name,
                    "is_staff": auth_user.is_staff,
                    "is_superuser": auth_user.is_superuser,
                    "is_active": auth_user.is_active,
                    "date_joined": auth_user.date_joined,
                    "last_login": auth_user.last_login,
                },
            )

            if not created:
                # Update existing user info to sync with auth service
                user.email = auth_user.email
                user.first_name = auth_user.first_name
                user.last_name = auth_user.last_name
                user.is_staff = auth_user.is_staff
                user.is_superuser = auth_user.is_superuser
                user.is_active = auth_user.is_active
                if auth_user.last_login:
                    user.last_login = auth_user.last_login
                user.save()
                logger.info(f"SharedDatabaseAuthBackend: Updated existing local user: {user.email}")
            else:
                logger.info(f"SharedDatabaseAuthBackend: Created new local user: {user.email}")

            return user

        except Exception as e:
            logger.error(f"SharedDatabaseAuthBackend: Error creating/updating local user: {str(e)}")
            return None


class CachedSharedDatabaseAuthBackend(SharedDatabaseAuthBackend):
    """
    Enhanced version with caching to reduce database queries.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate with caching to reduce database load.
        """
        if username is None or password is None:
            return None

        # Check cache for failed attempts (prevent brute force)
        cache_key = f"auth_fail_{username}"
        if cache.get(cache_key):
            logger.info(f"CachedSharedDatabaseAuthBackend: Cached failed attempt for: {username}")
            return None

        user = super().authenticate(request, username, password, **kwargs)

        if user is None:
            # Cache failed attempt for 5 minutes
            cache.set(cache_key, True, timeout=300)
            logger.info(f"CachedSharedDatabaseAuthBackend: Cached failed attempt for: {username}")

        return user
