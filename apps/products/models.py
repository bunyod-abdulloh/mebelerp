import uuid
from pathlib import Path

from django.db import models
from django.db.models import Q

from apps.core.choices import Currency, Unit
from apps.core.models import TimeStampedModel
from apps.core.validators import validate_image_size


def product_image_path(instance, filename):
    # Foydalanuvchi bergan nomga ishonmaymiz: faqat kengaytmani olamiz
    ext = Path(filename).suffix.lower()
    return f"products/{instance.product_id}/{uuid.uuid4().hex}{ext}"


class ProductCategory(TimeStampedModel):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Kategoriya nomi"
    )

    class Meta:
        verbose_name = "Mahsulot kategoriyasi"
        verbose_name_plural = "Mahsulot kategoriyalari"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Kategoriya"
    )
    name = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name="Mahsulot"
    )
    unit = models.CharField(
        max_length=5, choices=Unit.choices, default=Unit.PIECE, verbose_name="O'lchov birligi"
    )
    price = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Narx (1 birlik uchun)"
    )
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.UZS,
        verbose_name="Pul birligi"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Izoh"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Faol"
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(price__gte=0), name="product_price_gte_0"),
        ]

    def __str__(self):
        return f"{self.category} | {self.name}"


class ProductImage(TimeStampedModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="Mahsulot"
    )
    image = models.ImageField(
        upload_to=product_image_path,
        validators=[validate_image_size],
        verbose_name="Rasm"
    )

    class Meta:
        ordering = ["id"]  # birinchi rasm asosiy (cover) hisoblanadi
