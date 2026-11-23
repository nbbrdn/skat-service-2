from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .availability import with_availability
from .models import Part, StockBalance, SyncState

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


class PartIdentityTests(TestCase):
    def test_multiple_parts_can_omit_guid_and_share_a_code(self):
        first = Part.objects.create(name="Винт", price="10.00", code="0012")
        second = Part.objects.create(name="Болт", price="5.00", code="0012")
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertIsNone(first.external_id)
        self.assertIsNone(second.external_id)
        self.assertEqual(first.code, "0012")
        self.assertEqual(second.code, "0012")

    def test_filled_guid_is_unique(self):
        guid = uuid4()
        Part.objects.create(name="Винт", price="10.00", external_id=guid)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Part.objects.create(name="Болт", price="5.00", external_id=guid)


class StockAvailabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("stock-buyer")
        cls.part = Part.objects.create(name="Подшипник", price="20.00", code="000142", is_active=False)

    def setUp(self):
        self.client.force_login(self.user)
        self.now = timezone.now()
        self.sync = SyncState.objects.create(kind=SyncState.Kind.STOCK, last_success_at=self.now)

    def assert_availability(self, label, color="secondary"):
        response = self.client.get(reverse("parts:list"))
        self.assertContains(response, f'<span class="badge text-bg-{color}">{label}</span>', html=True)
        return response

    def test_missing_stock_balance(self):
        self.assert_availability("Наличие уточняется")

    def test_unknown_quantity(self):
        StockBalance.objects.create(part=self.part)
        self.assert_availability("Наличие уточняется")

    def test_positive_stock_displays_status_and_code_only(self):
        StockBalance.objects.create(part=self.part, quantity="831247.531")
        response = self.assert_availability("В наличии", "success")
        self.assertContains(response, "000142")
        self.assertContains(response, 'max="999"')
        self.assertNotContains(response, "831247")

    def test_zero_and_negative_stock(self):
        for quantity in ("0", "-0.001"):
            with self.subTest(quantity=quantity):
                StockBalance.objects.update_or_create(part=self.part, defaults={"quantity": quantity})
                self.assert_availability("Нет в наличии", "danger")

    def test_stale_sync_and_freshness_boundary(self):
        StockBalance.objects.create(part=self.part, quantity="0.001", received_at=self.now)
        self.sync.last_success_at = self.now - timedelta(minutes=15)
        self.sync.save()
        with patch("parts.availability.timezone.now", return_value=self.now):
            self.assert_availability("В наличии", "success")
        with patch("parts.availability.timezone.now", return_value=self.now + timedelta(seconds=1)):
            self.assert_availability("Наличие уточняется")

    def test_missing_sync_timestamp_or_row(self):
        StockBalance.objects.create(part=self.part, quantity="1")
        self.sync.last_success_at = None
        self.sync.save()
        self.assert_availability("Наличие уточняется")
        self.sync.delete()
        self.assert_availability("Наличие уточняется")

    def test_old_balance_with_fresh_global_sync(self):
        StockBalance.objects.create(part=self.part, quantity="1", received_at=self.now - timedelta(days=4))
        self.assert_availability("В наличии", "success")

    def test_availability_uses_constant_queries(self):
        Part.objects.bulk_create([Part(name=f"Деталь {index}", price="5.00") for index in range(10)])
        with self.assertNumQueries(2):
            statuses = [part.availability for part in with_availability(Part.objects.all())]
        self.assertEqual(statuses, ["Наличие уточняется"] * 11)

    def test_admin_stock_search_and_permissions(self):
        StockBalance.objects.create(part=self.part, quantity="4567.123")
        url = reverse("admin:parts_stockbalance_changelist")
        self.assertRedirects(self.client.get(url), f"{reverse('admin:login')}?next={url}")
        staff = get_user_model().objects.create_user("stock-staff", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(get_user_model().objects.create_superuser("stock-admin"))
        for query in ("000142", "Подшипник"):
            with self.subTest(query=query):
                self.assertContains(self.client.get(url, {"q": query}), "4567,123")
        sync_url = reverse("admin:parts_syncstate_change", args=[self.sync.pk])
        self.assertContains(self.client.get(sync_url), "Последняя успешная синхронизация")
        self.assertEqual(self.client.post(sync_url, {}).status_code, 403)


class StockMigrationTests(TransactionTestCase):
    def test_migration_preserves_existing_parts(self):
        old_target = [("parts", "0002_alter_part_id")]
        new_target = [("parts", "0003_stock_availability")]
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(new_target))

        executor = MigrationExecutor(connection)
        old_apps = executor.migrate(old_target).apps
        old_part = old_apps.get_model("parts", "Part")
        ids = [
            old_part.objects.create(name="Винт", price="12.50").pk,
            old_part.objects.create(name="Гайка", price="4.75").pk,
        ]

        new_apps = MigrationExecutor(connection).migrate(new_target).apps
        migrated_part = new_apps.get_model("parts", "Part")
        self.assertEqual(
            list(migrated_part.objects.filter(pk__in=ids).order_by("pk").values_list(
                "pk", "name", "price", "external_id", "code", "is_active",
            )),
            [
                (ids[0], "Винт", Decimal("12.50"), None, "", True),
                (ids[1], "Гайка", Decimal("4.75"), None, "", True),
            ],
        )
