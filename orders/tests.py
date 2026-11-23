from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from parts.models import Part
from .models import Order, OrderItem

User = get_user_model()

class ShopTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="safe-password-123")
        self.bob = User.objects.create_user("bob", password="safe-password-123")
        self.part = Part.objects.create(name="Корпус", price=Decimal("125.50"))
        self.other = Part.objects.create(name="Винт", price=Decimal("10.00"))

    def login_alice(self):
        self.client.force_login(self.alice)

    def add(self, part=None, qty=1):
        return self.client.post(reverse("orders:add", args=[(part or self.part).pk]), {"quantity": qty})

    def checkout(self, **data):
        cart = self.client.get(reverse("orders:cart"))
        return self.client.post(reverse("orders:checkout"), {
            "checkout_token": cart.context["checkout_token"],
            **data,
        })

    def test_auth_required(self):
        for name in ("parts:list", "orders:cart", "orders:history"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
        self.assertEqual(self.add().status_code, 302)
        self.assertFalse(Order.objects.exists())

    def test_add_with_quantity_and_cart_total(self):
        self.login_alice()
        self.add(qty=3)
        self.add(part=self.other, qty=2)
        response = self.client.get(reverse("orders:cart"))
        self.assertContains(response, "396,50")
        self.assertEqual(self.client.session["cart"], {str(self.part.pk): 3, str(self.other.pk): 2})

    def test_add_increment_and_limit(self):
        self.login_alice()
        self.add(qty=998)
        self.assertEqual(self.add(qty=2).status_code, 400)
        self.assertEqual(self.client.session["cart"][str(self.part.pk)], 998)

    def test_update_and_delete(self):
        self.login_alice()
        self.add()
        url = reverse("orders:update", args=[self.part.pk])
        self.client.post(url, {"quantity": 7})
        self.assertEqual(self.client.session["cart"][str(self.part.pk)], 7)
        self.assertEqual(self.client.post(url, {"quantity": 0}).status_code, 400)
        self.client.post(reverse("orders:remove", args=[self.part.pk]))
        self.assertEqual(self.client.session["cart"], {})

    def test_checkout_saves_price_and_name_snapshots(self):
        self.login_alice()
        self.add(qty=2)
        self.checkout()
        order = Order.objects.get()
        self.assertEqual(order.user, self.alice)
        self.assertEqual(order.total_amount, Decimal("251.00"))
        item = order.items.get()
        self.assertEqual((item.part_name, item.unit_price, item.quantity), ("Корпус", Decimal("125.50"), 2))
        self.assertEqual(self.client.session["cart"], {})
        self.part.name = "Новое название"
        self.part.price = Decimal("500.00")
        self.part.save()
        order.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(order.total_amount, Decimal("251.00"))
        self.assertEqual(item.part_name, "Корпус")
        self.assertEqual(item.unit_price, Decimal("125.50"))

    def test_checkout_uses_server_prices(self):
        self.login_alice()
        self.client.post(reverse("orders:add", args=[self.part.pk]), {"quantity": 1, "price": "0.01"})
        self.checkout(total_amount="0.01")
        self.assertEqual(Order.objects.get().total_amount, Decimal("125.50"))

    def test_empty_checkout_does_not_create_order(self):
        self.login_alice()
        self.checkout()
        self.assertFalse(Order.objects.exists())

    def test_checkout_cannot_be_submitted_with_get(self):
        self.login_alice()
        self.assertEqual(self.client.get(reverse("orders:checkout")).status_code, 405)

    def test_only_own_order_visible(self):
        self.login_alice()
        self.add()
        self.checkout()
        order = Order.objects.get()
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(reverse("orders:detail", args=[order.pk])).status_code, 404)
        history = self.client.get(reverse("orders:history"))
        self.assertNotContains(history, f"№ {order.pk}")

    def test_order_survives_deleted_part(self):
        self.login_alice()
        self.add()
        self.checkout()
        self.part.delete()
        item = OrderItem.objects.get()
        self.assertIsNone(item.part)
        self.assertEqual(item.part_name, "Корпус")

    def test_htmx_cart_edit_returns_fragment(self):
        self.login_alice()
        self.add(qty=2)
        response = self.client.post(reverse("orders:update", args=[self.part.pk]), {"quantity": 3}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="cart-main"')
        self.assertContains(response, 'hx-swap-oob="outerHTML"')

    def test_product_not_found_add_returns_404(self):
        self.login_alice()
        self.assertEqual(self.client.post(reverse("orders:add", args=[999999]), {"quantity": 1}).status_code, 404)

    def test_csrf_protects_cart_add(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alice)
        response = client.post(reverse("orders:add", args=[self.part.pk]), {"quantity": 1})
        self.assertEqual(response.status_code, 403)

    def test_admin_lists_submitted_orders(self):
        admin = User.objects.create_superuser("admin", "admin@example.org", "safe-password-123")
        self.login_alice()
        self.add(qty=2)
        self.checkout()
        self.client.force_login(admin)
        response = self.client.get(reverse("admin:orders_order_changelist"))
        self.assertContains(response, "alice")
        self.assertContains(response, "251")


    def test_invalid_quantities_leave_cart_unchanged(self):
        self.login_alice()
        self.add(qty=3)
        update_url = reverse("orders:update", args=[self.part.pk])
        for quantity in ("", "-1", "0", "1.5", "abc", "1000"):
            with self.subTest(quantity=quantity):
                self.assertEqual(self.add(qty=quantity).status_code, 400)
                self.assertEqual(self.client.post(update_url, {"quantity": quantity}).status_code, 400)
                self.assertEqual(self.client.session["cart"], {str(self.part.pk): 3})

    def test_deleted_cart_part_can_be_removed_before_checkout(self):
        self.login_alice()
        self.add()
        self.add(part=self.other, qty=2)
        token = self.client.get(reverse("orders:cart")).context["checkout_token"]
        remove_url = reverse("orders:remove", args=[self.part.pk])
        self.part.delete()

        response = self.client.post(reverse("orders:checkout"), {"checkout_token": token})
        self.assertRedirects(response, reverse("orders:cart"))
        self.assertFalse(Order.objects.exists())
        self.assertContains(self.client.get(reverse("orders:cart")), remove_url)

        response = self.client.post(remove_url, HTTP_HX_REQUEST="true")
        self.assertNotContains(response, "удалена из каталога")
        self.checkout()
        order = Order.objects.get()
        self.assertEqual(order.items.get().part, self.other)
        self.assertEqual(order.total_amount, Decimal("20.00"))

    def test_checkout_uses_price_and_name_at_checkout(self):
        self.login_alice()
        self.add(qty=2)
        self.part.name = "Обновлённое название"
        self.part.price = Decimal("50.00")
        self.part.save()
        self.assertContains(self.client.get(reverse("orders:cart")), "100,00")
        self.checkout()
        order = Order.objects.get()
        self.assertEqual(order.total_amount, Decimal("100.00"))
        item = order.items.get()
        self.assertEqual((item.part_name, item.unit_price), (self.part.name, self.part.price))

    def test_checkout_replay_does_not_create_another_order_or_clear_new_cart(self):
        self.login_alice()
        self.add()
        cart_url = reverse("orders:cart")
        response = self.client.get(cart_url)
        token = response.context["checkout_token"]
        self.assertContains(response, f'name="checkout_token" value="{token}"')
        url = reverse("orders:checkout")
        self.client.post(url, {"checkout_token": token})
        order = Order.objects.get()
        detail_url = reverse("orders:detail", args=[order.pk])
        self.assertRedirects(self.client.post(url, {"checkout_token": token}), detail_url)

        self.add(qty=2)
        self.assertRedirects(self.client.post(url, {"checkout_token": token}), detail_url)
        self.assertEqual(self.client.session["cart"], {str(self.part.pk): 2})
        self.assertEqual(Order.objects.count(), 1)
        self.checkout()
        self.assertEqual(Order.objects.count(), 2)

        self.client.force_login(self.bob)
        self.assertRedirects(self.client.post(url, {"checkout_token": token}), cart_url)
        self.assertEqual(Order.objects.count(), 2)

    def test_checkout_rejects_a_form_from_before_cart_update(self):
        self.login_alice()
        self.add()
        cart_url = reverse("orders:cart")
        token = self.client.get(cart_url).context["checkout_token"]
        self.add()
        response = self.client.post(reverse("orders:checkout"), {"checkout_token": token})
        self.assertRedirects(response, cart_url)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.client.session["cart"], {str(self.part.pk): 2})

    def test_legacy_session_cart_can_be_checked_out(self):
        self.login_alice()
        session = self.client.session
        session["cart"] = {str(self.part.pk): 2}
        session.save()
        self.checkout()
        self.assertEqual(Order.objects.get().items.get().quantity, 2)

    def test_order_pages_reject_changes(self):
        self.login_alice()
        self.add(qty=2)
        self.checkout()
        order = Order.objects.get()
        urls = [reverse("orders:history"), reverse("orders:detail", args=[order.pk])]
        for url in urls:
            self.assertEqual(self.client.post(url, {"total_amount": "0.01", "quantity": 99}).status_code, 405)
        order.refresh_from_db()
        self.assertEqual(order.total_amount, Decimal("251.00"))
        self.assertEqual(order.items.get().quantity, 2)

    def test_admin_order_detail_is_view_only(self):
        self.login_alice()
        self.add()
        self.checkout()
        order = Order.objects.get()
        admin = User.objects.create_superuser("admin")
        self.client.force_login(admin)
        url = reverse("admin:orders_order_change", args=[order.pk])
        self.assertContains(self.client.get(url), self.part.name)
        self.assertEqual(self.client.post(url, {"total_amount": "0.01"}).status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.total_amount, self.part.price)
