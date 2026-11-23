from django.test import SimpleTestCase
from django.urls import reverse


class HealthTests(SimpleTestCase):
    def test_public_health(self):
        response = self.client.get(reverse("health"), secure=True)
        self.assertContains(response, "ok\n", status_code=200)
        self.assertEqual(response.content, b"ok\n")
        self.assertEqual(response.headers["Content-Type"], "text/plain")
        self.assertFalse(response.cookies)

    def test_health_rejects_post(self):
        response = self.client.post(reverse("health"), secure=True)
        self.assertEqual(response.status_code, 405)
