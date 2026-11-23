from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="parts:list", permanent=False)),
    path("admin/", admin.site.urls),
    path("login/", LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("parts/", include("parts.urls")),
    path("", include("orders.urls")),
]
admin.site.site_header = "SKAT Service — администрирование"
admin.site.site_title = "SKAT Service"
admin.site.index_title = "Управление заказами и каталогом"
