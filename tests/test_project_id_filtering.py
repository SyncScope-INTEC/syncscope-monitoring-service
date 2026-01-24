"""
Tests for project_id filtering in monitoring views.
"""

import json
import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.monitoring.authentication import MonitoringUser
from apps.monitoring.models import CodeMetrics, DeveloperSession


class ProjectIdFilteringTest(APITestCase):
    """Tests for project_id filtering in views."""

    def setUp(self):
        self.client = APIClient()
        self.user_id = "12345678-1234-5678-9012-123456789abc"
        self.mock_user = MonitoringUser({"user_id": self.user_id, "email": "test@example.com", "username": "testuser"})
        self.client.force_authenticate(user=self.mock_user)

        self.project_id_1 = uuid.uuid4()
        self.project_id_2 = uuid.uuid4()

        # Create sessions
        self.session1 = DeveloperSession.objects.create(
            user_id=self.user_id, ide_name="VSCode", project_path=f"project_{self.project_id_1}"
        )
        self.session2 = DeveloperSession.objects.create(
            user_id=self.user_id, ide_name="PyCharm", project_path=f"project_{self.project_id_2}"
        )

        # Create metrics with project_id
        self.metric1 = CodeMetrics.objects.create(
            session=self.session1,
            project_id=self.project_id_1,
            file_path="file1.py",
            file_extension="py",
            lines_of_code=100,
        )
        self.metric2 = CodeMetrics.objects.create(
            session=self.session2,
            project_id=self.project_id_2,
            file_path="file2.py",
            file_extension="py",
            lines_of_code=200,
        )

    def test_filter_code_metrics_by_project_id(self):
        """Test filtering code metrics by project_id."""
        url = reverse("get_all_code_metrics")

        # Filter by project 1
        response = self.client.get(f"{url}?project_id={self.project_id_1}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["project_id"], str(self.project_id_1))

        # Filter by project 2
        response = self.client.get(f"{url}?project_id={self.project_id_2}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["project_id"], str(self.project_id_2))

    def test_submit_metrics_with_project_id(self):
        """Test submitting code metrics with project_id."""
        url = reverse("submit_code_metrics")
        new_project_id = uuid.uuid4()

        data = {
            "session": str(self.session1.session_id),
            "project_id": str(new_project_id),
            "file_path": "new_file.py",
            "lines_of_code": 50,
            "lines_added": 10,
            "lines_deleted": 0,
            "lines_modified": 0,
        }

        response = self.client.post(url, data=json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["project_id"], str(new_project_id))

        # Verify in DB
        metric = CodeMetrics.objects.get(metrics_id=response.data["metrics_id"])
        self.assertEqual(metric.project_id, new_project_id)
