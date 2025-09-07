"""
Models for accessing auth schema data directly from the shared database.
"""

from django.contrib.auth.hashers import check_password
from django.db import models


class AuthUser(models.Model):
    """
    Model representing users from the auth.users table.
    This allows us to authenticate against the shared database directly.
    """

    id = models.UUIDField(primary_key=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255, db_column='password_hash')
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(db_column='created_at')
    updated_at = models.DateTimeField(db_column='updated_at')
    last_login = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=50, default="UTC")
    role = models.CharField(max_length=20, default="developer")

    # Company relationship
    company_id = models.UUIDField(null=True, blank=True)

    class Meta:
        managed = False  # Django won't manage this table
        db_table = "auth.users"  # Direct reference to auth schema

    def check_password(self, raw_password):
        """
        Check if the provided password matches the user's password.
        """
        return check_password(raw_password, self.password_hash)

    def __str__(self):
        return self.email


class AuthCompany(models.Model):
    """
    Model representing companies from the auth.companies table.
    """

    id = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "auth.companies"

    def __str__(self):
        return self.name
