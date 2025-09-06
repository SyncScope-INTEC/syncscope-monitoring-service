"""
Custom admin authentication helpers and middleware.
"""

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.urls import reverse


class AuthServiceAdminSite(AdminSite):
    """
    Custom admin site with auth service integration.
    """

    site_header = "SyncScope Monitoring Service Administration"
    site_title = "SyncScope Monitoring Admin"
    index_title = "Monitoring Service Dashboard"

    def login(self, request, extra_context=None):
        """
        Custom login view with better error handling.
        """
        if request.method == "POST":
            username = request.POST.get("username")
            password = request.POST.get("password")

            if username and password:
                user = authenticate(request, username=username, password=password)
                if user is not None:
                    if user.is_active and (user.is_staff or user.is_superuser):
                        login(request, user)
                        return HttpResponseRedirect(request.GET.get("next", reverse("admin:index")))
                    else:
                        extra_context = extra_context or {}
                        extra_context["error_message"] = "Your account does not have admin privileges."
                else:
                    extra_context = extra_context or {}
                    extra_context["error_message"] = "Invalid credentials or auth service unavailable."

        return super().login(request, extra_context)


# Create custom admin site instance
monitoring_admin_site = AuthServiceAdminSite(name="monitoring_admin")


class AuthServiceUserAdmin(admin.ModelAdmin):
    """
    Custom user admin that shows auth service integration info.
    """

    list_display = ["username", "email", "first_name", "last_name", "is_staff", "is_superuser", "last_login"]
    list_filter = ["is_staff", "is_superuser", "is_active"]
    search_fields = ["username", "email", "first_name", "last_name"]
    readonly_fields = ["username", "email", "last_login", "date_joined"]

    fieldsets = (
        (None, {"fields": ("username", "email")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    def has_add_permission(self, request):
        # Users are created automatically from auth service
        return False

    def has_delete_permission(self, request, obj=None):
        # Users should be managed in the auth service
        return False


# Register with custom admin site
monitoring_admin_site.register(User, AuthServiceUserAdmin)
