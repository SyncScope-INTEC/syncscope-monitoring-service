"""
Tests for authentication models.
"""

import uuid
from datetime import datetime
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.utils import timezone

from apps.monitoring.auth_models import AuthCompany, AuthUser


class AuthUserTest(TestCase):
    """Tests for AuthUser model."""

    def setUp(self):
        self.user_data = {
            "id": uuid.uuid4(),
            "email": "test@example.com",
            "password_hash": make_password("testpassword"),
            "first_name": "Test",
            "last_name": "User",
            "is_active": True,
            "is_staff": False,
            "is_superuser": False,
            "created_at": timezone.now(),
            "updated_at": timezone.now(),
            "last_login": None,
            "timezone": "UTC",
            "role": "developer",
            "company_id": uuid.uuid4(),
        }

    def test_auth_user_creation(self):
        """Test AuthUser model creation and fields."""
        # Note: Since this is an unmanaged model, we can't actually create instances
        # in the database, but we can test the model structure and methods
        user = AuthUser(**self.user_data)

        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.first_name, "Test")
        self.assertEqual(user.last_name, "User")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.timezone, "UTC")
        self.assertEqual(user.role, "developer")

    def test_auth_user_str_method(self):
        """Test AuthUser string representation."""
        user = AuthUser(**self.user_data)
        self.assertEqual(str(user), "test@example.com")

    def test_check_password_correct(self):
        """Test password checking with correct password."""
        user = AuthUser(**self.user_data)
        self.assertTrue(user.check_password("testpassword"))

    def test_check_password_incorrect(self):
        """Test password checking with incorrect password."""
        user = AuthUser(**self.user_data)
        self.assertFalse(user.check_password("wrongpassword"))

    def test_check_password_empty(self):
        """Test password checking with empty password."""
        user = AuthUser(**self.user_data)
        self.assertFalse(user.check_password(""))

    def test_model_meta_configuration(self):
        """Test model meta configuration."""
        self.assertFalse(AuthUser._meta.managed)
        self.assertEqual(AuthUser._meta.db_table, "auth.users")

    def test_field_configurations(self):
        """Test field configurations and constraints."""
        # Test primary key
        id_field = AuthUser._meta.get_field("id")
        self.assertTrue(id_field.primary_key)

        # Test unique email field
        email_field = AuthUser._meta.get_field("email")
        self.assertTrue(email_field.unique)

        # Test password hash column name
        password_field = AuthUser._meta.get_field("password_hash")
        self.assertEqual(password_field.db_column, "password_hash")

        # Test created_at column name
        created_field = AuthUser._meta.get_field("created_at")
        self.assertEqual(created_field.db_column, "created_at")

        # Test updated_at column name
        updated_field = AuthUser._meta.get_field("updated_at")
        self.assertEqual(updated_field.db_column, "updated_at")

    def test_default_values(self):
        """Test model field defaults."""
        minimal_data = {
            "id": uuid.uuid4(),
            "email": "minimal@example.com",
            "password_hash": "hash",
            "created_at": timezone.now(),
            "updated_at": timezone.now(),
        }

        user = AuthUser(**minimal_data)

        # Test defaults
        self.assertTrue(user.is_active)  # Default True
        self.assertFalse(user.is_staff)  # Default False
        self.assertFalse(user.is_superuser)  # Default False
        self.assertEqual(user.timezone, "UTC")  # Default UTC
        self.assertEqual(user.role, "developer")  # Default developer
        self.assertEqual(user.first_name, "")  # Blank default
        self.assertEqual(user.last_name, "")  # Blank default

    def test_nullable_fields(self):
        """Test fields that can be null."""
        user = AuthUser(**self.user_data)

        # Test nullable fields can be None
        user.last_login = None
        user.company_id = None

        # Should not raise validation errors
        self.assertIsNone(user.last_login)
        self.assertIsNone(user.company_id)

    def test_staff_user_creation(self):
        """Test creating staff user."""
        staff_data = self.user_data.copy()
        staff_data.update({"email": "staff@example.com", "is_staff": True, "role": "admin"})

        user = AuthUser(**staff_data)
        self.assertTrue(user.is_staff)
        self.assertEqual(user.role, "admin")

    def test_superuser_creation(self):
        """Test creating superuser."""
        super_data = self.user_data.copy()
        super_data.update({"email": "super@example.com", "is_superuser": True, "is_staff": True, "role": "admin"})

        user = AuthUser(**super_data)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)


class AuthCompanyTest(TestCase):
    """Tests for AuthCompany model."""

    def setUp(self):
        self.company_data = {
            "id": uuid.uuid4(),
            "name": "Test Company Inc.",
            "domain": "testcompany.com",
            "created_at": timezone.now(),
            "updated_at": timezone.now(),
        }

    def test_auth_company_creation(self):
        """Test AuthCompany model creation and fields."""
        company = AuthCompany(**self.company_data)

        self.assertEqual(company.name, "Test Company Inc.")
        self.assertEqual(company.domain, "testcompany.com")
        self.assertIsNotNone(company.created_at)
        self.assertIsNotNone(company.updated_at)

    def test_auth_company_str_method(self):
        """Test AuthCompany string representation."""
        company = AuthCompany(**self.company_data)
        self.assertEqual(str(company), "Test Company Inc.")

    def test_model_meta_configuration(self):
        """Test AuthCompany model meta configuration."""
        self.assertFalse(AuthCompany._meta.managed)
        self.assertEqual(AuthCompany._meta.db_table, "auth.companies")

    def test_field_configurations(self):
        """Test AuthCompany field configurations."""
        # Test primary key
        id_field = AuthCompany._meta.get_field("id")
        self.assertTrue(id_field.primary_key)

        # Test unique domain field
        domain_field = AuthCompany._meta.get_field("domain")
        self.assertTrue(domain_field.unique)

        # Test field lengths
        name_field = AuthCompany._meta.get_field("name")
        self.assertEqual(name_field.max_length, 255)

        domain_field = AuthCompany._meta.get_field("domain")
        self.assertEqual(domain_field.max_length, 100)

    def test_company_with_different_domains(self):
        """Test companies with different domains."""
        company1 = AuthCompany(
            id=uuid.uuid4(), name="Company One", domain="company1.com", created_at=timezone.now(), updated_at=timezone.now()
        )

        company2 = AuthCompany(
            id=uuid.uuid4(), name="Company Two", domain="company2.com", created_at=timezone.now(), updated_at=timezone.now()
        )

        self.assertNotEqual(company1.domain, company2.domain)
        self.assertNotEqual(company1.name, company2.name)

    def test_company_fields_types(self):
        """Test company field types."""
        company = AuthCompany(**self.company_data)

        # Test UUID field
        self.assertIsInstance(company.id, uuid.UUID)

        # Test string fields
        self.assertIsInstance(company.name, str)
        self.assertIsInstance(company.domain, str)

        # Test datetime fields
        self.assertIsInstance(company.created_at, datetime)
        self.assertIsInstance(company.updated_at, datetime)


class AuthModelsIntegrationTest(TestCase):
    """Integration tests for auth models."""

    def test_user_company_relationship(self):
        """Test user-company relationship."""
        company_id = uuid.uuid4()

        company = AuthCompany(
            id=company_id, name="Test Company", domain="test.com", created_at=timezone.now(), updated_at=timezone.now()
        )

        user = AuthUser(
            id=uuid.uuid4(),
            email="employee@test.com",
            password_hash=make_password("password"),
            first_name="Employee",
            last_name="User",
            company_id=company_id,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        # Test relationship
        self.assertEqual(user.company_id, company.id)

    def test_multiple_users_same_company(self):
        """Test multiple users can belong to the same company."""
        company_id = uuid.uuid4()

        user1 = AuthUser(
            id=uuid.uuid4(),
            email="user1@company.com",
            password_hash=make_password("password1"),
            company_id=company_id,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        user2 = AuthUser(
            id=uuid.uuid4(),
            email="user2@company.com",
            password_hash=make_password("password2"),
            company_id=company_id,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        self.assertEqual(user1.company_id, user2.company_id)

    def test_user_without_company(self):
        """Test user can exist without company."""
        user = AuthUser(
            id=uuid.uuid4(),
            email="freelancer@example.com",
            password_hash=make_password("password"),
            company_id=None,  # No company
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        self.assertIsNone(user.company_id)

    @patch("apps.monitoring.auth_models.check_password")
    def test_password_checking_uses_django_hasher(self, mock_check):
        """Test that password checking uses Django's password hasher."""
        mock_check.return_value = True

        user = AuthUser(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash="hashed_password",
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        result = user.check_password("raw_password")

        self.assertTrue(result)
        mock_check.assert_called_once_with("raw_password", "hashed_password")
