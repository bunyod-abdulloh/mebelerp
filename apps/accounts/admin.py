from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    # Standart fieldset'larga o'zimizning maydonlarni qo'shamiz
    fieldsets = DjangoUserAdmin.fieldsets + (("Qo'shimcha", {"fields": ("role", "phone")}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (("Qo'shimcha", {"fields": ("role", "phone")}),)
    list_display = ("username", "get_full_name", "role", "is_active")
    list_filter = ("role", "is_active")