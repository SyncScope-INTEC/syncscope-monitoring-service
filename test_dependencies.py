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
        print(f"✅ Django {django.get_version()}")
        
        import rest_framework
        print("✅ Django REST Framework")
        
        # Celery
        import celery
        print(f"✅ Celery {celery.__version__}")
        
        import django_celery_beat
        print("✅ Django Celery Beat")
        
        # Database
        import psycopg2
        print("✅ psycopg2")
        
        # Redis
        import redis
        print("✅ Redis")
        
        # Testing
        import pytest
        print("✅ pytest")
        
        import coverage
        print("✅ coverage")
        
        # Utilities
        import decouple
        print("✅ python-decouple")
        
        import drf_spectacular
        print("✅ drf-spectacular")
        
        print("\n🎉 All dependencies imported successfully!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
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
        print("✅ Django Celery Beat models accessible")
        
        # Test REST Framework
        from rest_framework import status
        print("✅ Django REST Framework working")
        
        print("✅ Django compatibility test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Django compatibility error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 SyncScope Monitoring Service - Dependency Test")
    print("=" * 50)
    
    success = True
    
    success &= test_imports()
    success &= test_django_compatibility()
    
    if success:
        print("\n🎉 All dependency tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some dependency tests failed!")
        sys.exit(1)