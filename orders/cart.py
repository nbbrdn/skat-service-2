from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from django.utils.crypto import salted_hmac

from parts.models import Part

CART_KEY = "cart"
CHECKOUT_TOKEN_KEY = "checkout_token"
MAX_QUANTITY = 999

@dataclass(frozen=True)
class CartLine:
    part: Part
    quantity: int
    subtotal: Decimal


def get_cart(request):
    cart = request.session.get(CART_KEY, {})
    return cart if isinstance(cart, dict) else {}


def save_cart(request, cart):
    request.session[CART_KEY] = cart
    request.session[CHECKOUT_TOKEN_KEY] = uuid4().hex


def checkout_token(request):
    token = request.session.get(CHECKOUT_TOKEN_KEY)
    if token:
        return token
    # A cart saved before this field existed still needs a stable token.
    return salted_hmac("orders.checkout", request.session.session_key).hexdigest()[:32]


def cart_details(request):
    cart = get_cart(request)
    ids = [int(key) for key in cart if str(key).isdecimal()]
    parts = {str(part.pk): part for part in Part.objects.filter(pk__in=ids)}
    rows = []
    for key, raw_quantity in cart.items():
        part = parts.get(key)
        if not part:
            continue
        try:
            qty = int(raw_quantity)
        except (ValueError, TypeError):
            continue
        if 1 <= qty <= MAX_QUANTITY:
            rows.append(CartLine(part=part, quantity=qty, subtotal=part.price * qty))
    rows.sort(key=lambda row: (row.part.name.lower(), row.part.pk))
    total = sum((row.subtotal for row in rows), Decimal("0.00"))
    missing_ids = [pk for pk in ids if str(pk) not in parts]
    return {
        "rows": rows,
        "total": total,
        "missing_ids": missing_ids,
        "checkout_token": checkout_token(request) if rows else "",
    }
