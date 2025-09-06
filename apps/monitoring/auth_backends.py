"""
Authentication backends for monitoring service admin integration.
"""

import logging

import requests
from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AuthServiceBackend(BaseBackend):
    """
    Custom authentication backend that validates credentials against the auth service.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user against the auth service.
        """
        logger.info(f"AuthServiceBackend: Attempting authentication for user: {username}")

        if username is None or password is None:
            logger.warning("AuthServiceBackend: Username or password is None")
            return None

        # Try to authenticate with the auth service
        try:
            logger.info(f"AuthServiceBackend: Calling auth service for user: {username}")
            auth_response = self._authenticate_with_auth_service(username, password)
            if auth_response:
                logger.info(f"AuthServiceBackend: Auth service responded successfully for user: {username}")
                # Create or get the local user for Django admin
                user = self._get_or_create_local_user(auth_response)
                logger.info(f"AuthServiceBackend: Created/retrieved local user: {user}")
                return user
            else:
                logger.warning(f"AuthServiceBackend: Auth service authentication failed for user: {username}")
        except Exception as e:
            logger.error(f"Authentication error with auth service for user {username}: {str(e)}", exc_info=True)

        return None

    def get_user(self, user_id):
        """
        Get user by ID for session management.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def _authenticate_with_auth_service(self, username, password):
        """
        Make API call to auth service to validate credentials.
        """
        auth_service_url = getattr(settings, "AUTH_SERVICE_URL", "http://localhost:8000")
        login_url = f"{auth_service_url}/auth/login"

        logger.info(f"AuthServiceBackend: Using auth service URL: {auth_service_url}")
        logger.info(f"AuthServiceBackend: Calling login URL: {login_url}")

        payload = {"email": username, "password": password}  # Auth service uses email as username

        try:
            logger.info(f"AuthServiceBackend: Sending POST request to auth service")
            response = requests.post(login_url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)

            logger.info(f"AuthServiceBackend: Auth service response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                logger.info(f"AuthServiceBackend: Auth service login successful, checking staff status")
                # Verify this is a staff/admin user
                if self._is_staff_user(data.get("access_token")):
                    logger.info(f"AuthServiceBackend: User {username} is staff/admin, authentication successful")
                    return data
                else:
                    logger.warning(f"AuthServiceBackend: User {username} is not staff/admin")

            logger.warning(f"Auth service login failed: {response.status_code} - {response.text}")
            return None

        except requests.RequestException as e:
            logger.error(f"Failed to connect to auth service at {login_url}: {str(e)}")
            return None

    def _is_staff_user(self, access_token):
        """
        Check if the authenticated user has staff/admin privileges.
        """
        if not access_token:
            return False

        auth_service_url = getattr(settings, "AUTH_SERVICE_URL", "http://localhost:8000")
        profile_url = f"{auth_service_url}/auth/profile"

        try:
            response = requests.get(
                profile_url,
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 200:
                profile_data = response.json()
                # Check if user is staff or superuser
                return profile_data.get("is_staff", False) or profile_data.get("is_superuser", False)

        except requests.RequestException as e:
            logger.error(f"Failed to get user profile from auth service: {str(e)}")

        return False

    def _get_or_create_local_user(self, auth_response):
        """
        Create or update a local Django user for admin interface.
        """
        profile_data = self._get_user_profile(auth_response.get("access_token"))
        if not profile_data:
            return None

        email = profile_data.get("email")
        if not email:
            return None

        # Create or update local user
        user, created = User.objects.get_or_create(
            username=email,
            defaults={
                "email": email,
                "first_name": profile_data.get("first_name", ""),
                "last_name": profile_data.get("last_name", ""),
                "is_staff": profile_data.get("is_staff", False),
                "is_superuser": profile_data.get("is_superuser", False),
                "is_active": profile_data.get("is_active", True),
            },
        )

        if not created:
            # Update existing user info
            user.email = email
            user.first_name = profile_data.get("first_name", user.first_name)
            user.last_name = profile_data.get("last_name", user.last_name)
            user.is_staff = profile_data.get("is_staff", False)
            user.is_superuser = profile_data.get("is_superuser", False)
            user.is_active = profile_data.get("is_active", True)
            user.save()

        # Cache the auth token for this user session
        cache.set(f"auth_token_{user.id}", auth_response.get("access_token"), timeout=3600)

        return user

    def _get_user_profile(self, access_token):
        """
        Get user profile from auth service.
        """
        if not access_token:
            return None

        auth_service_url = getattr(settings, "AUTH_SERVICE_URL", "http://localhost:8000")
        profile_url = f"{auth_service_url}/auth/profile"

        try:
            response = requests.get(
                profile_url,
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 200:
                return response.json()

        except requests.RequestException as e:
            logger.error(f"Failed to get user profile: {str(e)}")

        return None


class CachedAuthServiceBackend(AuthServiceBackend):
    """
    Enhanced version with caching to reduce API calls to auth service.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate with caching to reduce auth service load.
        """
        if username is None or password is None:
            return None

        # Check cache first (short-lived cache for failed attempts)
        cache_key = f"auth_fail_{username}"
        if cache.get(cache_key):
            return None

        user = super().authenticate(request, username, password, **kwargs)

        if user is None:
            # Cache failed attempt for 5 minutes to prevent brute force
            cache.set(cache_key, True, timeout=300)

        return user
