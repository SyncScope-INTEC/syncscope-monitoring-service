"""
Authentication utilities for service-to-service communication.
"""

import logging

import jwt
import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ServiceAuthManager:
    def __init__(self):
        self.auth_service_url = settings.AUTH_SERVICE_URL
        self.jwt_secret = settings.JWT_SECRET_KEY

    def verify_user_token(self, token):
        """Verify user JWT token with auth service."""
        try:
            # Try to decode locally first
            decoded = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return decoded
        except jwt.InvalidTokenError:
            # Fallback to auth service verification
            return self._verify_with_auth_service(token)

    def _verify_with_auth_service(self, token):
        """Verify token with auth service."""
        try:
            response = requests.post(f"{self.auth_service_url}/auth/verify-token/", json={"token": token}, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except requests.RequestException as e:
            logger.error(f"Failed to verify token with auth service: {e}")
            return None

    def get_user_info(self, user_id):
        """Get user information from auth service."""
        cache_key = f"user_info:{user_id}"
        cached_info = cache.get(cache_key)

        if cached_info:
            return cached_info

        try:
            response = requests.get(f"{self.auth_service_url}/auth/users/{user_id}/", timeout=10)
            if response.status_code == 200:
                user_info = response.json()
                cache.set(cache_key, user_info, 300)  # Cache for 5 minutes
                return user_info
            return None
        except requests.RequestException as e:
            logger.error(f"Failed to get user info from auth service: {e}")
            return None


def get_user_from_request(request):
    """Extract user information from request."""
    auth_header = request.META.get("HTTP_AUTHORIZATION")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    auth_manager = ServiceAuthManager()
    user_data = auth_manager.verify_user_token(token)

    if user_data:
        return user_data.get("user_id")
    return None
