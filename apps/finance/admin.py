from django.contrib import admin

from .models import ExchangeRate, Payment, Expense


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("date", "usd_to_uzs")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("paid_at", "order", "method", "amount", "currency", "order_amount", "created_by")
    list_filter = ("method", "currency")
    search_fields = ("order__customer__name", "order__customer__phone")
    date_hierarchy = "paid_at"
    autocomplete_fields = ("order",)
    readonly_fields = ("created_by",)
    list_select_related = ("order__customer", "created_by")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("date", "category", "amount", "currency", "method", "created_by")
    list_filter = ("category", "currency", "method")
    search_fields = ("note",)
    date_hierarchy = "date"
    readonly_fields = ("created_by",)
    list_select_related = ("created_by",)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_owner  # o'chirish hisobotni o'zgartiradi

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
