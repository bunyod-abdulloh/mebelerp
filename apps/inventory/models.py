from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce

from apps.core.models import TimeStampedModel

ZERO = Decimal("0")


class MovementType(models.TextChoices):
    IN = "in", "Kirim"
    OUT = "out", "Chiqim"


class MaterialQuerySet(models.QuerySet):
    def with_balance(self):
        # Qoldiq = kirimlar yig'indisi - chiqimlar yig'indisi (bitta SQL so'rovda)
        total_in = Coalesce(
            Sum("movements__quantity", filter=Q(movements__movement_type=MovementType.IN)), ZERO
        )
        total_out = Coalesce(
            Sum("movements__quantity", filter=Q(movements__movement_type=MovementType.OUT)), ZERO
        )
        return self.annotate(balance=total_in - total_out)

    def low_stock(self):
        # Telegram bot ogohlantirishi ham shu metoddan foydalanadi
        return self.with_balance().filter(is_active=True, balance__lte=F("min_quantity"))


class MaterialCategory(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)  # MDF, DSP, Fanera, Furnitura...

    class Meta:
        verbose_name_plural = "material categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Material(TimeStampedModel):
    class Unit(models.TextChoices):
        PIECE = "piece", "dona"
        SHEET = "sheet", "list"
        SQM = "sqm", "m²"
        METER = "meter", "metr"
        KG = "kg", "kg"
        LITER = "liter", "litr"

    category = models.ForeignKey(MaterialCategory, on_delete=models.PROTECT, related_name="materials")
    name = models.CharField(max_length=255, unique=True)
    unit = models.CharField(max_length=10, choices=Unit.choices)
    min_quantity = models.DecimalField(
        "Minimal qoldiq", max_digits=12, decimal_places=3, default=ZERO,
        help_text="Qoldiq shu miqdorga yetganda yoki kamayganda ogohlantirish beriladi.",
    )
    is_active = models.BooleanField(default=True)

    objects = MaterialQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(min_quantity__gte=0), name="material_min_quantity_gte_0"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_unit_display()})"

    def get_balance(self) -> Decimal:
        # Qoldiq mantig'i faqat with_balance()da: ikki joyda takrorlanmaydi
        return type(self).objects.with_balance().values_list("balance", flat=True).get(pk=self.pk)


class StockMovement(TimeStampedModel):
    class Reason(models.TextChoices):
        PURCHASE = "purchase", "Xarid (kirim)"
        PRODUCTION = "production", "Ishlab chiqarishga sarf"
        WASTE = "waste", "Brak / yo'qotish"
        ADJUSTMENT = "adjustment", "Tuzatish (inventarizatsiya)"

    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=3, choices=MovementType.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)  # doim musbat, ishorani type beradi
    reason = models.CharField(max_length=20, choices=Reason.choices)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, null=True, blank=True,
        related_name="material_movements",
        help_text="Ishlab chiqarish sarfi bo'lsa, qaysi buyurtma uchun.",
    )
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stock_movements",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="stockmovement_quantity_gt_0"),
        ]
        indexes = [
            # Qoldiq hisoblash so'rovlarini tezlashtiradi
            models.Index(fields=["material", "movement_type"]),
        ]

    def __str__(self):
        sign = "+" if self.movement_type == MovementType.IN else "-"
        return f"{self.material.name}: {sign}{self.quantity}"

    def _ensure_enough_stock(self):
        balance = self.material.get_balance()
        if self.quantity > balance:
            raise ValidationError(
                f"Omborda yetarli {self.material.name} yo'q: mavjud {balance} {self.material.get_unit_display()}."
            )

    def clean(self):
        super().clean()
        # Formada tushunarli xato uchun (qulflamaydi, shuning uchun yakuniy himoya emas)
        if self._state.adding and self.material_id and self.quantity and self.movement_type == MovementType.OUT:
            self._ensure_enough_stock()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Ombor harakatini o'zgartirib bo'lmaydi. Tuzatish uchun teskari harakat kiriting.")
        with transaction.atomic():
            # Material qatorini qulflaymiz: bir vaqtdagi chiqimlar navbat bilan tekshiriladi
            Material.objects.select_for_update().get(pk=self.material_id)
            if self.movement_type == MovementType.OUT:
                self._ensure_enough_stock()
            super().save(*args, **kwargs)
