from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import TimeStampedModel

phone_validator = RegexValidator(
    regex=r"^\+998\d{9}$",
    message="Telefon raqami +998901234567 formatida bo'lishi kerak.",
)


class Customer(TimeStampedModel):
    class Type(models.TextChoices):
        INDIVIDUAL = "individual", "Jismoniy shaxs"
        COMPANY = "company", "Korxona"

    customer_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.INDIVIDUAL,
        verbose_name="Mijoz turi"
    )
    name = models.CharField(
        verbose_name="Ism-familiya / korxona nomi",
        max_length=255,
        db_index=True
    )
    phone = models.CharField(
        max_length=13,
        verbose_name="Telefon raqam",
        validators=[phone_validator],
        db_index=True
    )
    address = models.TextField(
        blank=True,
        verbose_name="Manzil"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Faol"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CustomerNote(TimeStampedModel):
    """Mijoz bilan muloqot tarixi: kim, qachon, nima haqida gaplashgan."""

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="notes",
        verbose_name="Mijoz"
    )
    text = models.TextField(
        verbose_name="Izoh"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,  # xodim ketsa ham izoh qoladi
        null=True,
        verbose_name="Xodim",
        related_name="customer_notes",
    )

    class Meta:
        ordering = ["-created_at"]
