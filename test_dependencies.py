#!/usr/bin/env python3
"""
Test script to verify all dependencies are working correctly
"""
import sys

def test_imports():
    """Test that all critical dependencies can be imported"""
    
    print("Testing dependency imports...")
    
    try:
        # Django and related packages
        import django
        print(f"[OK] Django {django.get_version()}")
        
        import rest_framework
        print("[OK] Django REST Framework")
        
        # Celery
        import celery
        print(f"[OK] Celery {celery.__version__}")
        
        import django_celery_beat
        print("[OK] Django Celery Beat")
        
        # Database
        import psycopg2
        print("[OK] psycopg2")
        
        # Redis
        import redis
        print("[OK] Redis")
        
        # Testing
        import pytest
        print("[OK] pytest")
        
        import coverage
        print("[OK] coverage")
        
        # Utilities
        import decouple
        print("[OK] python-decouple")
        
        import drf_spectacular
        print("[OK] drf-spectacular")
        
        print("\n[SUCCESS] All dependencies imported successfully!")
        return True
        
    except ImportError as e:
        print(f"[ERROR] Import error: {e}")
        return False

def test_django_compatibility():
    """Test Django-specific compatibility"""
    
    print("\nTesting Django compatibility...")
    
    try:
        import os
        import django
        from django.conf import settings
        
        # Configure Django settings for testing
        if not settings.configured:
            settings.configure(
                DEBUG=True,
                SECRET_KEY='test-secret-key-for-dependency-check',
                INSTALLED_APPS=[
                    'django.contrib.contenttypes',
                    'django.contrib.auth',
                    'rest_framework',
                    'django_celery_beat',
                ],
                DATABASES={
                    'default': {
                        'ENGINE': 'django.db.backends.sqlite3',
                        'NAME': ':memory:',
                    }
                },
                USE_TZ=True,
            )
        
        django.setup()
        
        # Test Celery Beat models
        from django_celery_beat.models import PeriodicTask
        print("[OK] Django Celery Beat models accessible")
        
        # Test REST Framework
        from rest_framework import status
        print("[OK] Django REST Framework working")
        
        print("[SUCCESS] Django compatibility test passed!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Django compatibility error: {e}")
        return False

if __name__ == "__main__":
    print("Testing SyncScope Monitoring Service Dependencies")
    print("=" * 50)
    
    success = True
    
    success &= test_imports()
    success &= test_django_compatibility()
    
    if success:
        print("\n[SUCCESS] All dependency tests passed!")
        sys.exit(0)
    else:
        print("\n[ERROR] Some dependency tests failed!")
        sys.exit(1)