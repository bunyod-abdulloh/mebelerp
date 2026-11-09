from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Customer, CustomerNote


class CustomerNoteInline(admin.TabularInline):
    model = CustomerNote
    extra = 0
    readonly_fields = ("created_by", "created_at")


@admin.register(Customer)
class CustomerAdmin(ModelAdmin):
    list_display = ("name", "customer_type", "phone", "is_active")
    list_filter = ("customer_type", "is_active")
    search_fields = ("name", "phone")
    inlines = [CustomerNoteInline]

    def save_formset(self, request, form, formset, change):
        # Izoh muallifini avtomatik qo'yamiz, qo'lda tanlab bo'lmasin
        instances = formset.save(commit=False)
        for obj in instances:
            if isinstance(obj, CustomerNote) and obj.created_by is None:
                obj.created_by = request.user
            obj.save()
        formset.save_m2m()
