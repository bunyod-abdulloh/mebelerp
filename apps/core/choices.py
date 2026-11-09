from django.db import models


class Currency(models.TextChoices):
    UZS = "UZS", "So'm"
    USD = "USD", "AQSH dollari"


class Unit(models.TextChoices):
    PIECE = "pcs", "dona"
    METER = "m", "metr"
    SQUARE_METER = "m2", "m²"
    CUBIC_METER = "m3", "m³"
    KILOGRAM = "kg", "kg"
