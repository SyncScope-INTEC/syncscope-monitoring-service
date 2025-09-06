"""
Debug views for testing auth service integration.
"""

import json

import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@csrf_exempt
@require_http_methods(["POST"])
def test_auth_service(request):
    """
    Test endpoint to verify auth service connectivity and authentication.
    """
    try:
        data = json.loads(request.body)
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return JsonResponse({"error": "Username and password required", "status": "failed"}, status=400)

        # Test auth service connectivity
        auth_service_url = getattr(settings, "AUTH_SERVICE_URL", "http://localhost:8000")
        login_url = f"{auth_service_url}/auth/login"

        result = {"auth_service_url": auth_service_url, "login_url": login_url, "status": "testing"}

        # Test login
        payload = {"email": username, "password": password}

        try:
            response = requests.post(login_url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)

            result["login_response_status"] = response.status_code
            result["login_response_text"] = response.text[:500]  # Limit response size

            if response.status_code == 200:
                login_data = response.json()
                access_token = login_data.get("access_token")

                if access_token:
                    # Test profile endpoint
                    profile_url = f"{auth_service_url}/auth/profile"

                    profile_response = requests.get(
                        profile_url,
                        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                        timeout=10,
                    )

                    result["profile_response_status"] = profile_response.status_code
                    result["profile_response_text"] = profile_response.text[:500]

                    if profile_response.status_code == 200:
                        profile_data = profile_response.json()
                        result["user_info"] = {
                            "email": profile_data.get("email"),
                            "is_staff": profile_data.get("is_staff"),
                            "is_superuser": profile_data.get("is_superuser"),
                            "is_active": profile_data.get("is_active"),
                        }
                        result["status"] = "success"
                    else:
                        result["status"] = "profile_failed"
                else:
                    result["status"] = "no_token"
            else:
                result["status"] = "login_failed"

        except requests.RequestException as e:
            result["error"] = str(e)
            result["status"] = "connection_failed"

        return JsonResponse(result)

    except Exception as e:
        return JsonResponse({"error": str(e), "status": "error"}, status=500)


@require_http_methods(["GET"])
def test_settings(request):
    """
    Test endpoint to check current settings.
    """
    return JsonResponse(
        {
            "AUTH_SERVICE_URL": getattr(settings, "AUTH_SERVICE_URL", "Not set"),
            "AUTHENTICATION_BACKENDS": settings.AUTHENTICATION_BACKENDS,
            "DEBUG": settings.DEBUG,
            "ENVIRONMENT": getattr(settings, "ENVIRONMENT", "Not set"),
        }
    )
