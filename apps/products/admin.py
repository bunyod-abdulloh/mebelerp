from django.contrib import admin
from unfold.admin import TabularInline, ModelAdmin

from .models import Product, ProductCategory, ProductImage
from ..core.formatting import format_money


class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 1


@admin.register(ProductCategory)
class ProductCategoryAdmin(ModelAdmin):
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ("category", "name", "price_display", "currency", "is_active")
    list_filter = ("category", "currency", "is_active")
    search_fields = ("name",)
    inlines = [ProductImageInline]

    @admin.display(description="Narxi")
    def price_display(self, obj):
        return format_money(getattr(obj, "price", None))
