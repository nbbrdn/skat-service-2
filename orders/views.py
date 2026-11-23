from decimal import Decimal
from uuid import UUID

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST, require_safe

from parts.models import Part
from .cart import MAX_QUANTITY, cart_details, checkout_token, get_cart, save_cart
from .forms import QuantityForm
from .models import Order, OrderItem


def _htmx(request):
    return request.headers.get("HX-Request") == "true"


def _render_cart_fragment(request):
    return HttpResponse(
        render_to_string("orders/partials/cart_main.html", cart_details(request), request=request)
        + render_to_string("orders/partials/cart_count_oob.html", request=request)
    )


@login_required
@require_POST
def add_to_cart(request, pk):
    get_object_or_404(Part, pk=pk)
    form = QuantityForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Количество должно быть от 1 до 999", status=400)
    cart = get_cart(request).copy()
    old = int(cart.get(str(pk), 0))
    new = old + form.cleaned_data["quantity"]
    if new > MAX_QUANTITY:
        return HttpResponse("В корзине может быть не более 999 единиц одной запчасти", status=400)
    cart[str(pk)] = new
    save_cart(request, cart)
    if _htmx(request):
        return HttpResponse(
            render_to_string("orders/partials/add_result.html", request=request)
            + render_to_string("orders/partials/cart_count_oob.html", request=request)
        )
    messages.success(request, "Запчасть добавлена в корзину")
    return redirect("parts:list")


@login_required
def cart_view(request):
    return render(request, "orders/cart.html", cart_details(request))


@login_required
@require_POST
def update_cart(request, pk):
    cart = get_cart(request).copy()
    if str(pk) not in cart:
        return HttpResponse("Такой позиции в корзине нет", status=404)
    form = QuantityForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Количество должно быть от 1 до 999", status=400)
    cart[str(pk)] = form.cleaned_data["quantity"]
    save_cart(request, cart)
    if _htmx(request):
        return _render_cart_fragment(request)
    return redirect("orders:cart")


@login_required
@require_POST
def remove_from_cart(request, pk):
    cart = get_cart(request).copy()
    cart.pop(str(pk), None)
    save_cart(request, cart)
    if _htmx(request):
        return _render_cart_fragment(request)
    return redirect("orders:cart")


@login_required
@require_POST
def checkout(request):
    cart = get_cart(request)
    submitted_token = request.POST.get("checkout_token", "")
    try:
        token = UUID(hex=submitted_token)
    except ValueError:
        token = None
    if token:
        existing = Order.objects.filter(user=request.user, checkout_token=token).first()
        if existing:
            return redirect("orders:detail", pk=existing.pk)
    if not cart:
        messages.error(request, "Корзина пуста")
        return redirect("orders:cart")
    if not token or token.hex != checkout_token(request):
        messages.error(request, "Корзина изменилась. Проверьте позиции")
        return redirect("orders:cart")

    quantities = {}
    for key, raw_quantity in cart.items():
        form = QuantityForm({"quantity": raw_quantity})
        if not key.isascii() or not key.isdecimal() or not form.is_valid():
            messages.error(request, "Некорректная позиция в корзине")
            return redirect("orders:cart")
        quantities[int(key)] = form.cleaned_data["quantity"]

    # Insert first so concurrent submissions compete for the same unique token.
    # Any failure rolls back both the order and the token.
    try:
        with transaction.atomic():
            order = Order.objects.create(user=request.user, checkout_token=token)
            parts = list(Part.objects.select_for_update().filter(pk__in=quantities).order_by("pk"))
            if len(parts) != len(cart):
                raise ValidationError("Состав корзины изменился. Проверьте позиции")
            order.total_amount = sum(
                (part.price * quantities[part.pk] for part in parts), Decimal("0.00")
            )
            total_field = Order._meta.get_field("total_amount")
            try:
                total_field.run_validators(order.total_amount)
            except ValidationError:
                raise ValidationError("Сумма заказа превышает допустимый предел") from None
            order.save(update_fields=["total_amount"])
            OrderItem.objects.bulk_create([
                OrderItem(order=order, part=part, part_name=part.name,
                          unit_price=part.price, quantity=quantities[part.pk])
                for part in parts
            ])
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("orders:cart")
    except IntegrityError:
        existing = Order.objects.filter(user=request.user, checkout_token=token).first()
        if existing:
            return redirect("orders:detail", pk=existing.pk)
        raise

    save_cart(request, {})
    messages.success(request, f"Заказ №{order.pk} оформлен")
    return redirect("orders:detail", pk=order.pk)


@login_required
@require_safe
def order_history(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items")
    return render(request, "orders/history.html", {"orders": orders})


@login_required
@require_safe
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk, user=request.user)
    return render(request, "orders/detail.html", {"order": order})
