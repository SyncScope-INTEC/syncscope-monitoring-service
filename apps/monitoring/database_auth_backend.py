"""
API-based authentication backend that uses the SyncScope Auth Service.
"""

import logging
import os
import sys
import time
import uuid

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.core.cache import cache
from django.db import connection

User = get_user_model()

logger = logging.getLogger(__name__)

# Check if we're in test/CI environment
IS_TEST_ENVIRONMENT = (
    "test" in sys.argv
    or "pytest" in sys.modules
    or os.environ.get("GITHUB_ACTIONS")
    or settings.DEBUG
    and hasattr(settings, "USE_SQLITE")
    and settings.USE_SQLITE
)


class SimplePKField:
    """Mock primary key field to mimic Django's field behavior"""

    def value_to_string(self, user):
        """Convert user ID to string for session storage"""
        return str(user.id)

    def to_python(self, value):
        """Convert string back to UUID for session retrieval"""
        if value is None:
            return value
        # If it's already a UUID, return as string
        if isinstance(value, uuid.UUID):
            return str(value)
        # If it's a string representation of UUID, return as-is
        return str(value)


class SimpleMeta:
    """Mock _meta class to make SimpleUser compatible with Django's session management"""

    def __init__(self):
        self.pk = SimplePKField()


class SimpleUser:
    """
    Simple user class that mimics Django's User for authentication purposes.
    Works directly with auth.users table via database queries.
    """

    _meta = SimpleMeta()

    def __init__(
        self,
        id,
        email,
        first_name,
        last_name,
        is_staff,
        is_active,
        is_superuser,
        last_login,
    ):
        self.id = id
        self.email = email
        self.username = email  # Use email as username for Django compatibility
        self.first_name = first_name or ""
        self.last_name = last_name or ""
        self.is_staff = is_staff or False
        self.is_active = is_active or True
        self.is_superuser = is_superuser or False
        self.last_login = last_login
        self.is_authenticated = True
        self.is_anonymous = False

    @property
    def pk(self):
        """Primary key property for Django compatibility"""
        return self.id

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    def save(self, *args, **kwargs):
        """Override save to prevent any database writes"""
        pass

    def set_password(self, password):
        """Override to prevent password changes"""
        pass

    @staticmethod
    def get_user_by_id(user_id):
        """Get user by ID from auth.users table"""
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, email, first_name, last_name, is_staff, is_active, is_superuser, last_login
                    FROM auth.users
                    WHERE id = %s AND is_active = true
                """,
                    [str(user_id)],
                )

                user_data = cursor.fetchone()
                if user_data:
                    return SimpleUser(*user_data)
                return None
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            return None

    @staticmethod
    def get_user_by_email(email):
        """Get user by email from auth.users table"""
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, email, first_name, last_name, is_staff, is_active, is_superuser, last_login
                    FROM auth.users
                    WHERE email = %s AND is_active = true
                """,
                    [email],
                )

                user_data = cursor.fetchone()
                if user_data:
                    return SimpleUser(*user_data)
                return None
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None


class AuthServiceAPIBackend(BaseBackend):
    """
    Authentication backend that uses the SyncScope Auth Service API.
    Handles cold starts and provides proper service separation.
    """

    def __init__(self):
        self.auth_service_url = settings.AUTH_SERVICE_URL

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user via the Auth Service API.
        """
        logger.info(f"AuthServiceAPIBackend: Attempting authentication for user: {username}")

        if username is None or password is None:
            logger.warning("AuthServiceAPIBackend: Username or password is None")
            return None

        try:
            # Authenticate with the auth service
            auth_response = self._authenticate_with_service(username, password)

            if auth_response and auth_response.get("user"):
                user_data = auth_response["user"]
                logger.info(f"AuthServiceAPIBackend: Authentication successful for: {username}")

                # Check if user has admin privileges
                role = user_data.get("role", "developer")
                is_staff = user_data.get("is_staff", False) or role in ["admin", "supervisor"]
                is_superuser = user_data.get("is_superuser", False) or role == "admin"

                if user_data.get("is_active", True) and is_staff:
                    logger.info(f"AuthServiceAPIBackend: User {username} has admin privileges (role: {role})")

                    # Create or update local Django user for admin interface
                    user = self._get_or_create_local_user(user_data)
                    logger.info(f"AuthServiceAPIBackend: Created/updated local user: {user}")
                    return user
                else:
                    logger.warning(f"AuthServiceAPIBackend: User {username} does not have admin privileges")
            else:
                logger.warning(f"AuthServiceAPIBackend: Authentication failed for: {username}")

        except Exception as e:
            logger.error(f"AuthServiceAPIBackend: Error during authentication: {str(e)}", exc_info=True)

        return None

    def get_user(self, user_id):
        """
        Get user by ID for session management.
        """
        if IS_TEST_ENVIRONMENT:
            # In test environment, use Django's default User model
            try:
                return User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return None
        else:
            # In production, use SimpleUser with direct database queries
            return SimpleUser.get_user_by_id(user_id)

    def _authenticate_with_service(self, email, password, max_retries=3):
        """
        Authenticate with the auth service, handling cold starts with retries.
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"AuthServiceAPIBackend: API call attempt {attempt + 1}/{max_retries}")

                response = requests.post(
                    f"{self.auth_service_url}/auth/login/",
                    json={"email": email, "password": password},
                    headers={"Content-Type": "application/json"},
                    timeout=30,  # Longer timeout for cold starts
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code in [401, 403]:
                    # Authentication failed - don't retry
                    logger.warning(f"AuthServiceAPIBackend: Authentication failed with status {response.status_code}")
                    return None
                else:
                    logger.warning(f"AuthServiceAPIBackend: API call failed with status {response.status_code}")

            except requests.exceptions.Timeout:
                logger.warning(f"AuthServiceAPIBackend: Timeout on attempt {attempt + 1} (cold start?)")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
            except requests.exceptions.RequestException as e:
                logger.warning(f"AuthServiceAPIBackend: Request failed on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Brief wait before retry

        logger.error(f"AuthServiceAPIBackend: All {max_retries} attempts failed")
        return None

    def _get_or_create_local_user(self, user_data):
        """
        Get or create a User from auth service data.
        Environment-aware: uses Django User in tests, SimpleUser in production.
        """
        try:
            email = user_data["email"]
            auth_service_uuid = user_data.get("id")  # UUID from auth service
            role = user_data.get("role", "developer")

            # Check if user has admin privileges
            is_staff = user_data.get("is_staff", False) or role in ["admin", "supervisor"]
            is_superuser = user_data.get("is_superuser", False) or role == "admin"

            if user_data.get("is_active", True) and is_staff:
                logger.info(f"AuthServiceAPIBackend: User {email} has admin privileges (role: {role})")

                if IS_TEST_ENVIRONMENT:
                    # In test environment, use Django's default User model
                    try:
                        user = User.objects.get(email=email)
                        # Update user data
                        user.first_name = user_data.get("first_name", "")
                        user.last_name = user_data.get("last_name", "")
                        user.is_staff = is_staff
                        user.is_active = user_data.get("is_active", True)
                        user.is_superuser = is_superuser
                        user.save()
                        logger.info(f"AuthServiceAPIBackend: Updated existing Django user: {user.email}")
                        return user
                    except User.DoesNotExist:
                        # Create new Django user
                        user = User.objects.create_user(
                            username=email,
                            email=email,
                            first_name=user_data.get("first_name", ""),
                            last_name=user_data.get("last_name", ""),
                            is_staff=is_staff,
                            is_active=user_data.get("is_active", True),
                            is_superuser=is_superuser,
                        )
                        logger.info(f"AuthServiceAPIBackend: Created Django user: {user.email}")
                        return user
                    except Exception as e:
                        # Handle any database errors during Django User operations
                        logger.error(f"AuthServiceAPIBackend: Database error with Django User: {str(e)}")
                        return None
                else:
                    # In production, use SimpleUser with direct database queries
                    user = SimpleUser.get_user_by_id(auth_service_uuid)

                    if user:
                        logger.info(f"AuthServiceAPIBackend: Found existing user: {user.email}")
                        return user
                    else:
                        # Create a SimpleUser object representing the auth service user
                        user = SimpleUser(
                            id=auth_service_uuid,
                            email=email,
                            first_name=user_data.get("first_name", ""),
                            last_name=user_data.get("last_name", ""),
                            is_staff=is_staff,
                            is_active=user_data.get("is_active", True),
                            is_superuser=is_superuser,
                            last_login=None,
                        )

                        logger.info(
                            f"AuthServiceAPIBackend: Created SimpleUser for: {user.email} with UUID: {auth_service_uuid}"
                        )
                        return user
            else:
                logger.warning(f"AuthServiceAPIBackend: User {email} does not have admin privileges")
                return None

        except Exception as e:
            logger.error(f"AuthServiceAPIBackend: Error creating/updating local user: {str(e)}")
            return None


class CachedAuthServiceAPIBackend(AuthServiceAPIBackend):
    """
    Enhanced API-based authentication with caching to reduce API calls and prevent brute force.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate with caching to reduce API load and prevent brute force attacks.
        """
        if username is None or password is None:
            return None

        # Check cache for failed attempts (prevent brute force)
        cache_key = f"auth_fail_{username}"
        if cache.get(cache_key):
            logger.info(f"CachedAuthServiceAPIBackend: Cached failed attempt for: {username}")
            return None

        user = super().authenticate(request, username, password, **kwargs)

        if user is None:
            # Cache failed attempt for 5 minutes
            cache.set(cache_key, True, timeout=300)
            logger.info(f"CachedAuthServiceAPIBackend: Cached failed attempt for: {username}")

        return user
