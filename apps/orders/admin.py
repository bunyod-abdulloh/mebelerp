from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse, path
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.views.decorators.http import require_GET
from unfold.admin import TabularInline, ModelAdmin
from unfold.widgets import UnfoldAdminDecimalFieldWidget

from apps.finance.models import Payment
from apps.products.models import Product
from .models import Order, OrderItem, OrderStatusHistory
from ..core.formatting import format_money


def make_status_action(target):
    @admin.action(description=Order.Status(target).label)
    def action(modeladmin, request, queryset):
        for order in queryset:
            try:
                order.change_status(target, request.user)
            except ValidationError as e:
                modeladmin.message_user(request, f"{order.number}: {e.messages[0]}", messages.ERROR)

    action.__name__ = f"set_status_{target}"
    return action


class PaymentInline(TabularInline):
    model = Payment
    extra = 0
    tab = True
    verbose_name = "To'lov"
    verbose_name_plural = "To'lovlar"
    fields = ("paid_at", "method", "amount", "currency", "usd_rate", "order_amount", "note", "created_by")
    readonly_fields = ("order_amount", "created_by")  # created_by save_formset da qo'yiladi

    def has_change_permission(self, request, obj=None):
        return False  # mavjud to'lov faqat ko'rinadi, yangisi qo'shiladi

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        if not super().has_add_permission(request, obj):  # finance.add_payment huquqi
            return False
        return obj is not None and obj.status != Order.Status.CANCELLED


class OrderAddForm(forms.ModelForm):
    initial_payment = forms.DecimalField(
        label="To'langan summa", required=False, min_value=Decimal("0"),
        max_digits=16, decimal_places=2, initial=Decimal("0"),
        help_text="Buyurtma valyutasida. Qarzdan ayriladi.",
        widget=UnfoldAdminDecimalFieldWidget,
    )

    class Meta:
        model = Order
        fields = "__all__"


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 1
    autocomplete_fields = ("product",)
    tab = True
    verbose_name = "Mahsulot"
    verbose_name_plural = "Mahsulotlar"

    class Media:
        js = ("orders/js/order_item_autofill.js",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "product":
            # Widget RelatedFieldWidgetWrapper ichida o'ralgan bo'ladi
            widget = getattr(field.widget, "widget", field.widget)
            widget.attrs["data-product-url"] = reverse("admin:orders_order_product_data")
        return field

    def _editable(self, obj):
        return obj is None or obj.status not in Order.FINAL_STATUSES

    def has_add_permission(self, request, obj=None):
        return self._editable(obj)

    def has_change_permission(self, request, obj=None):
        return self._editable(obj)

    def has_delete_permission(self, request, obj=None):
        return self._editable(obj)


class StatusHistoryInline(TabularInline):
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    show_change_link = False
    tab = True  # tab qilmoqchi bo'lsangiz; hozir u olib tashlangan
    verbose_name = "Holat o'zgarishi"
    verbose_name_plural = "Buyurtmalar holati tarixi"

    fields = ("created_at", "from_status", "to_status", "changed_by")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        # Tarixni ko'rish ota buyurtmani ko'rish huquqiga bog'liq bo'lsin
        return request.user.has_perm("orders.view_order")


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ("number_display", "customer", "status", "deadline", "currency",
                    "total_display", "paid_display", "debt_display")
    list_filter = ("status", "currency", "deadline")
    list_editable = ("status",)
    search_fields = ("number", "customer__name", "customer__phone")
    date_hierarchy = "order_date"
    autocomplete_fields = ("customer",)
    list_select_related = ("customer",)
    inlines = [OrderItemInline, StatusHistoryInline]
    actions = [make_status_action(s) for s in (
        Order.Status.IN_PRODUCTION, Order.Status.READY, Order.Status.DELIVERED, Order.Status.CANCELLED
    )]

    change_form_before_template = "orders/order_summary.html"

    def get_inlines(self, request, obj):
        inlines = [OrderItemInline, StatusHistoryInline]
        if obj is not None:  # yangi buyurtmada initial_payment ishlatiladi
            inlines.insert(1, PaymentInline)
        return inlines

    def save_formset(self, request, form, formset, change):
        if formset.model is not Payment:
            return super().save_formset(request, form, formset, change)
        for payment in formset.save(commit=False):
            payment.created_by = request.user
            try:
                payment.save()  # qulf + qarz tekshiruvi shu yerda
            except ValidationError as e:
                self.message_user(request, f"To'lov yozilmadi: {e.messages[0]}", messages.ERROR)

    def get_queryset(self, request):
        return super().get_queryset(request).with_totals()

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ["status", "created_by"]
        return ["status", "created_by", "currency_display", "customer"]

    def get_exclude(self, request, obj=None):
        # Mavjud buyurtmada currency formada bo'lmaydi, uning o'rniga currency_display ko'rinadi
        return ["currency"] if obj else None

    def get_urls(self):
        custom = [
            path(
                "product-data/",
                self.admin_site.admin_view(self.product_data_view),
                name="orders_order_product_data",
            ),
        ]
        return custom + super().get_urls()

    def has_delete_permission(self, request, obj=None):
        # super() Django'ning delete_order huquqini tekshiradi: uni faqat kerakli userlarga bering
        if not super().has_delete_permission(request, obj):
            return False
        if obj is None:  # ro'yxat darajasi: "delete selected" action ko'rinishi uchun
            return True
        return obj.status == Order.Status.NEW and not obj.payments.exists()

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            super().save_model(request, obj, form, change)
            return

        if "status" not in form.changed_data:
            super().save_model(request, obj, form, change)
            return

        new_status = obj.status
        old_status = (
            Order.objects
            .values_list("status", flat=True)
            .get(pk=obj.pk)
        )

        obj.status = old_status

        try:
            obj.change_status(new_status, request.user)
        except ValidationError as e:
            self.message_user(
                request,
                f"{obj.number}: {e.messages[0]}",
                messages.ERROR,
            )

    @admin.display(description="ID", ordering="number")
    def number_display(self, obj):
        return obj.number

    @admin.display(description="Jami", ordering="total")
    def total_display(self, obj):
        return format_money(getattr(obj, "total", None))

    @admin.display(description="To'langan", ordering="paid")
    def paid_display(self, obj):
        return format_money(getattr(obj, "paid", None))

    @admin.display(description="Qarz", ordering="debt")
    def debt_display(self, obj):
        return format_money(getattr(obj, "debt", None))

    @method_decorator(require_GET)
    def product_data_view(self, request):
        if not request.user.has_perm("products.view_product"):
            raise PermissionDenied
        try:
            pk = int(request.GET.get("product", ""))
        except ValueError:
            return JsonResponse({"error": "invalid product"}, status=400)

        product = get_object_or_404(Product, pk=pk, is_active=True)
        return JsonResponse({
            "name": product.name,
            "unit": product.unit,
            "unit_price": str(product.price),  # Decimal'ni float qilmaymiz
            "currency": product.currency,
        })

    @admin.display(description="Valyuta")
    def currency_display(self, obj):
        # JS mavjud buyurtma valyutasini shu elementdan o'qiydi
        return format_html(
            '<span id="order-currency" data-code="{}">{}</span>',
            obj.currency, obj.get_currency_display(),
        )

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:  # faqat yangi buyurtmada
            kwargs["form"] = OrderAddForm
        return super().get_form(request, obj, **kwargs)

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        if obj is not None:
            cancelled = obj.status == Order.Status.CANCELLED
            context["order_summary"] = {
                "total": f"{format_money(getattr(obj, 'total', None))} {obj.currency}",
                "paid": f"{format_money(getattr(obj, 'paid', None))} {obj.currency}",
                # Bekor qilingan buyurtma qarz hisoblanmaydi (with_debt() bilan bir xil qoida)
                "debt": "—" if cancelled else f"{format_money(getattr(obj, 'debt', None))} {obj.currency}",
            }
        return super().render_change_form(request, context, add, change, form_url, obj)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)  # items avval saqlansin
        if change:
            return
        amount = form.cleaned_data.get("initial_payment") or Decimal("0")
        if amount <= 0:
            return
        order = form.instance
        try:
            Payment.objects.create(
                order=order,
                amount=amount,
                currency=order.currency,  # buyurtma valyutasida: kurs kerak emas
                created_by=request.user,
            )
        except ValidationError as e:
            self.message_user(
                request,
                f"Buyurtma saqlandi, lekin to'lov yozilmadi: {e.messages[0]}",
                messages.WARNING,
            )
