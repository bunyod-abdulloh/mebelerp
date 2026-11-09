import uuid
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.choices import Currency
from apps.core.models import TimeStampedModel
from apps.core.validators import validate_document_size
from apps.orders.models import Order

CENT = Decimal("0.01")


class ExchangeRate(TimeStampedModel):
    date = models.DateField(unique=True)
    usd_to_uzs = models.DecimalField("1 USD = ? so'm", max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.CheckConstraint(condition=Q(usd_to_uzs__gt=0), name="exchangerate_gt_0"),
        ]

    def __str__(self):
        return f"{self.date}: {self.usd_to_uzs}"

    @classmethod
    def latest_rate(cls):
        rate = cls.objects.order_by("-date").first()
        return rate.usd_to_uzs if rate else None


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Naqd pul"
        CARD = "card", "Bank kartasi"
        TRANSFER = "transfer", "Bank o'tkazmasi"
        OTHER = "other", "Boshqa"

    order = models.ForeignKey(
        Order,
        verbose_name="Buyurtma",
        on_delete=models.PROTECT,
        related_name="payments"
    )
    method = models.CharField(
        verbose_name="To'lov turi",
        max_length=10,
        choices=Method.choices,
        default=Method.CASH
    )
    amount = models.DecimalField(
        verbose_name="Summa",
        max_digits=14,
        decimal_places=2
    )
    currency = models.CharField(
        verbose_name="Pul birligi",
        max_length=3,
        choices=Currency.choices,
        default=Currency.UZS
    )
    usd_rate = models.DecimalField(
        verbose_name="Kurs (1 USD = ? so'm)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Faqat buyurtma valyutasidan farqli to'lovda. Bo'sh qolsa, oxirgi kurs olinadi.",
    )
    order_amount = models.DecimalField(
        verbose_name="Buyurtma valyutasidagi summa",
        help_text="To'lov paytidagi kurs bo'yicha avtomatik hisoblanadi.",
        max_digits=16, decimal_places=2, editable=False,
    )
    paid_at = models.DateTimeField(
        verbose_name="To'langan sana",
        default=timezone.now
    )
    note = models.TextField(
        verbose_name="Izoh",
        blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Xodim",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    class Meta:
        ordering = ["-paid_at"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_gt_0"),
            models.CheckConstraint(
                condition=Q(usd_rate__isnull=True) | Q(usd_rate__gt=0), name="payment_usd_rate_gt_0"
            ),
        ]
        indexes = [models.Index(fields=["paid_at"])]  # davr bo'yicha hisobotlar

    def __str__(self):
        return f"{self.order.number}: {self.amount} {self.currency}"

    def _to_order_currency(self, order_currency) -> Decimal:
        if self.currency == order_currency:
            self.usd_rate = None
            return self.amount
        rate = self.usd_rate or ExchangeRate.latest_rate()
        if not rate:
            raise ValidationError("Valyuta kursi kiritilmagan. Kursni ko'rsating yoki ExchangeRate qo'shing.")
        self.usd_rate = rate
        converted = self.amount * rate if self.currency == Currency.USD else self.amount / rate
        return converted.quantize(CENT, rounding=ROUND_HALF_UP)

    def _validate_against(self, order):
        if order.status == Order.Status.CANCELLED:
            raise ValidationError("Bekor qilingan buyurtmaga to'lov qabul qilib bo'lmaydi.")
        self.order_amount = self._to_order_currency(order.currency)
        debt = order.get_debt()
        if self.order_amount > debt:
            raise ValidationError(f"To'lov qarzdan oshib ketdi: qolgan qarz {debt} {order.currency}.")

    def clean(self):
        super().clean()
        # Formada tushunarli xato uchun (qulflamaydi, yakuniy himoya emas)
        if self._state.adding and self.order_id and self.amount:
            self._validate_against(self.order)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("To'lovni o'zgartirib bo'lmaydi.")
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=self.order_id)  # navbat bilan tekshirish
            self._validate_against(order)
            super().save(*args, **kwargs)


def expense_document_path(instance, filename):
    # Foydalanuvchi bergan nomga ishonmaymiz: faqat kengaytma qoladi
    return f"expenses/{instance.date:%Y/%m}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class Expense(TimeStampedModel):
    class Category(models.TextChoices):
        FOOD = "food", "Oziq-ovqat"
        SALARY = "salary", "Maosh va avanslar"
        UTILITIES = "utilities", "Elektr va kommunal"
        MATERIALS = "materials", "Xomashyo va furnitura"
        TRANSPORT = "transport", "Yetkazib berish va transport"
        OTHER = "other", "Boshqa"

    category = models.CharField(max_length=20, choices=Category.choices)
    date = models.DateField(default=timezone.localdate)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.UZS)
    method = models.CharField(max_length=10, choices=Payment.Method.choices, default=Payment.Method.CASH)
    note = models.TextField(blank=True)
    document = models.FileField(
        upload_to=expense_document_path, blank=True,
        validators=[FileExtensionValidator(["pdf", "jpg", "jpeg", "png"]), validate_document_size],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="expenses",
    )

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="expense_amount_gt_0"),
        ]
        indexes = [models.Index(fields=["date", "category"])]  # davr bo'yicha hisobotlar

    def __str__(self):
        return f"{self.get_category_display()}: {self.amount} {self.currency}"
