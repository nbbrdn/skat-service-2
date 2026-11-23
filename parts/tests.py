from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Part

class CatalogTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("buyer", password="safe-password-123")
        self.client.force_login(self.user)
        Part.objects.create(name="Пружина", price=Decimal("20.00"))
        Part.objects.create(name="Болт", price=Decimal("10.00"))

    def test_catalog_lists_products(self):
        response = self.client.get(reverse("parts:list"))
        self.assertContains(response, "Пружина")
        self.assertContains(response, "Болт")

    def test_search_filters(self):
        response = self.client.get(reverse("parts:list"), {"q": "Болт"})
        self.assertContains(response, "Болт")
        self.assertNotContains(response, "Пружина")
