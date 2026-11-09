from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.choices import Currency, Unit
from apps.core.models import TimeStampedModel
from apps.orders.utils import order_number

ZERO = Decimal("0")
MONEY = DecimalField(max_digits=16, decimal_places=2)


class OrderQuerySet(models.QuerySet):
    def with_totals(self):
        """subtotal, total, paid, debt ustunlarini qo'shadi.

        Har bir yig'indi alohida Subquery: ikkita JOIN qatorlarni ko'paytirib yuboradi.
        """
        Payment = apps.get_model("finance", "Payment")
        items_sum = (
            OrderItem.objects.filter(order=OuterRef("pk")).order_by().values("order")
            .annotate(s=Sum(F("quantity") * F("unit_price"), output_field=MONEY)).values("s")
        )
        paid_sum = (
            Payment.objects.filter(order=OuterRef("pk")).order_by().values("order")
            .annotate(s=Sum("order_amount")).values("s")
        )
        return (
            self.annotate(
                subtotal=Coalesce(Subquery(items_sum, output_field=MONEY), ZERO, output_field=MONEY),
                paid=Coalesce(Subquery(paid_sum, output_field=MONEY), ZERO, output_field=MONEY),
            )
            .annotate(total=ExpressionWrapper(F("subtotal") - F("discount"), output_field=MONEY))
            .annotate(debt=ExpressionWrapper(F("total") - F("paid"), output_field=MONEY))
        )

    def with_debt(self):
        # Bekor qilingan buyurtma qarz emas, pozitsiyalari bo'lsa ham
        return self.exclude(status=Order.Status.CANCELLED).with_totals().filter(debt__gt=0)

    def overdue(self):
        # Qarzdorlar ro'yxati va Telegram eslatmalari uchun
        return self.with_debt().filter(payment_due_date__lt=timezone.localdate())


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "Yangi"
        IN_PRODUCTION = "in_production", "Ishlab chiqarilmoqda"
        READY = "ready", "Tayyor"
        DELIVERED = "delivered", "Yetkazildi"
        CANCELLED = "cancelled", "Bekor qilindi"

    # Qaysi holatdan qaysilariga o'tish mumkin
    TRANSITIONS = {
        Status.NEW: {Status.IN_PRODUCTION, Status.CANCELLED},
        Status.IN_PRODUCTION: {Status.READY, Status.CANCELLED},
        Status.READY: {Status.DELIVERED, Status.IN_PRODUCTION, Status.CANCELLED},
        Status.DELIVERED: set(),
        Status.CANCELLED: set(),
    }
    FINAL_STATUSES = (Status.DELIVERED, Status.CANCELLED)
    number = models.CharField(
        verbose_name="Buyurtma raqami",
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        editable=False
    )

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="Mijoz")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW
    )
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.UZS,
        verbose_name="Pul birligi")
    discount = models.DecimalField(
        "Chegirma (buyurtma valyutasida)", max_digits=16, decimal_places=2, default=ZERO
    )
    order_date = models.DateField(
        default=timezone.localdate,
        verbose_name="Buyurtma sanasi"
    )
    deadline = models.DateField(
        verbose_name="Topshirish sanasi"
    )
    payment_due_date = models.DateField(
        verbose_name="To'lov sanasi",
        null=True,
        blank=True
    )
    note = models.TextField(
        verbose_name="Izoh",
        blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_orders",
        verbose_name="Xodim"
    )

    objects = OrderQuerySet.as_manager()

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(condition=Q(discount__gte=0), name="order_discount_gte_0"),
            models.CheckConstraint(condition=Q(deadline__gte=F("order_date")), name="order_deadline_gte_date"),
        ]
        indexes = [
            models.Index(fields=["status", "deadline"]),  # muddati yaqinlashganlarni topish
            models.Index(fields=["payment_due_date"]),
        ]

    def __str__(self):
        return f"{self.number} - {self.customer.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            self.number = order_number(self.pk)
            # update(): save() ni qayta chaqirmaymiz, rekursiya va ortiqcha updated_at bo'lmaydi
            type(self).objects.filter(pk=self.pk).update(number=self.number)

    def get_debt(self) -> Decimal:
        return type(self).objects.with_totals().values_list("debt", flat=True).get(pk=self.pk)

    def change_status(self, new_status, user=None):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=self.pk)  # joriy holatni qulf bilan o'qiymiz
            if new_status not in self.TRANSITIONS[order.status]:
                raise ValidationError(
                    f"{order.get_status_display()} holatidan {self.Status(new_status).label} holatiga o'tib bo'lmaydi."
                )
            if new_status == self.Status.CANCELLED and order.payments.exists():
                raise ValidationError("To'lov qabul qilingan buyurtmani bekor qilib bo'lmaydi.")
            OrderStatusHistory.objects.create(
                order=order, from_status=order.status, to_status=new_status, changed_by=user
            )
            order.status = new_status
            order.save(update_fields=["status", "updated_at"])  # auto_now ham yangilansin
        self.status = new_status


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Buyurtma"
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Mahsulot",
        help_text="Tayyor mahsulot yoki katalogdagi mebel. Xizmat yoki maxsus buyurtmada bo'sh qoldiriladi.",
    )
    unit = models.CharField(
        max_length=5, choices=Unit.choices, default=Unit.PIECE, verbose_name="Birlik"
    )
    quantity = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal("1"), verbose_name="Miqdor"
    )
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,  # buyurtma valyutasida, snapshot
        verbose_name="Dona narxi"
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="orderitem_quantity_gt_0"),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="orderitem_unit_price_gte_0"),
        ]

    def __str__(self):
        return f"{self.product.name} x{self.quantity.normalize()} {self.get_unit_display()}"

    @property
    def line_total(self) -> Decimal:
        return self.quantity * self.unit_price

    def _ensure_editable(self):
        if self.order.status in Order.FINAL_STATUSES:
            raise ValidationError("Yakunlangan buyurtma tarkibini o'zgartirib bo'lmaydi.")

    def clean(self):
        super().clean()
        if self.product.name and self.product_id is None:
            raise ValidationError("Nom yoki mahsulot ko'rsatilishi kerak.")

        if self.unit == Unit.PIECE and self.quantity != self.quantity.to_integral_value():
            raise ValidationError({"quantity": "Dona birligida miqdor butun son bo'lishi kerak."})

        if self.order_id:  # yangi buyurtma inline'ida order hali yo'q
            self._ensure_editable()

    def save(self, *args, **kwargs):
        self._ensure_editable()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._ensure_editable()
        return super().delete(*args, **kwargs)


class OrderStatusHistory(TimeStampedModel):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history",
        verbose_name="Buyurtma"
    )
    from_status = models.CharField(
        max_length=20,
        choices=Order.Status.choices,
        verbose_name="Holatdan"
    )
    to_status = models.CharField(
        max_length=20,
        choices=Order.Status.choices,
        verbose_name="Holatga"
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="O'zgartirdi",
        related_name="order_changed"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="O'zgartirilgan vaqt/sana"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Buyurtma holati tarixi"

    def __str__(self):
        return self.order.number
