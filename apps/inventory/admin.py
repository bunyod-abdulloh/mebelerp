from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Material, MaterialCategory, StockMovement


class LowStockFilter(admin.SimpleListFilter):
    title = "qoldiq holati"
    parameter_name = "stock"

    def lookups(self, request, model_admin):
        return [("low", "Kam qolgan"), ("ok", "Yetarli")]

    def queryset(self, request, queryset):
        if self.value() == "low":
            return queryset.low_stock()
        if self.value() == "ok":
            return queryset.exclude(pk__in=queryset.low_stock().values("pk"))
        return queryset


@admin.register(MaterialCategory)
class MaterialCategoryAdmin(ModelAdmin):
    search_fields = ("name",)


@admin.register(Material)
class MaterialAdmin(ModelAdmin):
    list_display = ("name", "category", "unit", "balance_display", "min_quantity", "is_low", "is_active")
    list_filter = ("category", "is_active", LowStockFilter)
    search_fields = ("name",)  # StockMovement'dagi autocomplete uchun shart
    list_select_related = ("category",)

    def get_queryset(self, request):
        return super().get_queryset(request).with_balance()

    def get_readonly_fields(self, request, obj=None):
        # Harakatlar bo'lgach birlikni o'zgartirib bo'lmaydi
        return ("unit",) if obj else ()

    @admin.display(description="Qoldiq", ordering="balance")
    def balance_display(self, obj):
        return obj.balance

    @admin.display(description="Kam qolgan", boolean=True)
    def is_low(self, obj):
        return obj.balance <= obj.min_quantity


@admin.register(StockMovement)
class StockMovementAdmin(ModelAdmin):
    list_display = ("created_at", "material", "movement_type", "quantity", "reason", "created_by")
    list_filter = ("movement_type", "reason", "material__category")
    search_fields = ("material__name", "note")
    date_hierarchy = "created_at"
    autocomplete_fields = ("material", "order")
    list_select_related = ("material", "created_by", "order")
    readonly_fields = ("created_by",)

    def has_change_permission(self, request, obj=None):
        return False  # o'zgarmas tarix

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.created_by = request.user  # muallifni formadan emas, sessiyadan olamiz
        super().save_model(request, obj, form, change)
