from django.contrib import admin
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ("part_name", "unit_price", "quantity", "line_total_display")
    readonly_fields = fields

    @admin.display(description="Сумма, ₽")
    def line_total_display(self, obj):
        return obj.line_total

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at", "total_amount")
    list_filter = ("created_at",)
    search_fields = ("=id", "user__username", "user__email")
    readonly_fields = ("user", "created_at", "total_amount")
    fields = readonly_fields
    inlines = [OrderItemInline]
    list_select_related = ("user",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
