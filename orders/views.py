from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from parts.models import Part
from .cart import CART_KEY, MAX_QUANTITY, cart_details, get_cart, save_cart
from .forms import QuantityForm
from .models import Order, OrderItem


def _htmx(request):
    return request.headers.get("HX-Request") == "true"


def _render_cart_fragment(request):
    rows, total = cart_details(request)
    return HttpResponse(
        render_to_string("orders/partials/cart_main.html", {"rows": rows, "total": total}, request=request)
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
    rows, total = cart_details(request)
    return render(request, "orders/cart.html", {"rows": rows, "total": total})


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
    if not cart:
        messages.error(request, "Корзина пуста")
        return redirect("orders:cart")
    # Never trust names, prices or totals submitted by the browser.
    with transaction.atomic():
        ids = [int(k) for k in cart if str(k).isdecimal()]
        parts = {str(part.pk): part for part in Part.objects.select_for_update().filter(pk__in=ids)}
        if len(parts) != len(cart):
            messages.error(request, "Состав корзины изменился. Проверьте позиции")
            return redirect("orders:cart")
        rows = []
        for key, raw_quantity in cart.items():
            try:
                quantity = int(raw_quantity)
            except (ValueError, TypeError):
                quantity = 0
            if not 1 <= quantity <= MAX_QUANTITY:
                messages.error(request, "Некорректное количество в корзине")
                return redirect("orders:cart")
            part = parts[key]
            rows.append((part, quantity))
        total = sum((p.price * qty for p, qty in rows), start=0)
        order = Order.objects.create(user=request.user, total_amount=total)
        OrderItem.objects.bulk_create([
            OrderItem(order=order, part=part, part_name=part.name, unit_price=part.price, quantity=qty)
            for part, qty in rows
        ])
    save_cart(request, {})
    messages.success(request, f"Заказ №{order.pk} оформлен")
    return redirect("orders:detail", pk=order.pk)


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items")
    return render(request, "orders/history.html", {"orders": orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk, user=request.user)
    return render(request, "orders/detail.html", {"order": order})
