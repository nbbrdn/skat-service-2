from django.contrib import admin

from .models import Part, StockBalance, SyncState


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "price", "is_active")
    search_fields = ("name", "code")
    list_per_page = 50


@admin.register(StockBalance)
class StockBalanceAdmin(admin.ModelAdmin):
    list_display = ("part", "quantity", "source_version", "source_updated_at", "received_at")
    list_select_related = ("part",)
    search_fields = ("part__code", "part__name")
    autocomplete_fields = ("part",)


@admin.register(SyncState)
class SyncStateAdmin(admin.ModelAdmin):
    list_display = ("kind", "last_success_at")
    readonly_fields = ("kind", "last_success_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
