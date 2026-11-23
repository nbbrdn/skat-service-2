from django.urls import path
from . import views

app_name = "orders"
urlpatterns = [
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<int:pk>/", views.add_to_cart, name="add"),
    path("cart/update/<int:pk>/", views.update_cart, name="update"),
    path("cart/remove/<int:pk>/", views.remove_from_cart, name="remove"),
    path("cart/checkout/", views.checkout, name="checkout"),
    path("orders/", views.order_history, name="history"),
    path("orders/<int:pk>/", views.order_detail, name="detail"),
]
