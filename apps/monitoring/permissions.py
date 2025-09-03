"""
Custom permissions for monitoring service.
"""

from rest_framework import permissions

from .authentication import MonitoringUser


class IsAuthenticated(permissions.BasePermission):
    """
    Allows access only to authenticated users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of a session or admins to access it.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # Admin users can access everything
        if hasattr(request.user, "is_staff") and request.user.is_staff:
            return True

        # Object owner can access their own data
        if hasattr(obj, "user_id"):
            return obj.user_id == request.user.user_id

        # For session-related objects, check session owner
        if hasattr(obj, "session") and hasattr(obj.session, "user_id"):
            return obj.session.user_id == request.user.user_id

        return False


class CanAccessUserData(permissions.BasePermission):
    """
    Permission to check if user can access specific user data.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Get user_id from URL parameters
        user_id = view.kwargs.get("user_id")
        if not user_id:
            return True  # No specific user restriction

        # Admin users can access any user data
        if hasattr(request.user, "is_staff") and request.user.is_staff:
            return True

        # Users can only access their own data
        return str(request.user.user_id) == str(user_id)


class IsMonitoringService(permissions.BasePermission):
    """
    Permission for service-to-service communication.
    """

    def has_permission(self, request, view):
        # Allow service-to-service calls
        service_token = request.META.get("HTTP_X_SERVICE_TOKEN")
        if service_token:
            # In a real implementation, verify the service token
            # For now, allow any service token
            return True

        # Regular user authentication
        return bool(request.user and request.user.is_authenticated)
