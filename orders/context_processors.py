from .cart import MAX_QUANTITY, get_cart

def cart_count(request):
    count = 0
    for value in get_cart(request).values():
        try:
            quantity = int(value)
        except (ValueError, TypeError):
            continue
        if 1 <= quantity <= MAX_QUANTITY:
            count += quantity
    return {"cart_count": count}
