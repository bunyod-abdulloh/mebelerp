from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Material, MaterialCategory, MovementType, StockMovement


class StockMovementTests(TestCase):
    def setUp(self):
        category = MaterialCategory.objects.create(name="MDF")
        self.mdf = Material.objects.create(
            category=category, name="MDF 18mm oq", unit=Material.Unit.SHEET, min_quantity=Decimal("5")
        )

    def move(self, movement_type, quantity, reason=StockMovement.Reason.PURCHASE):
        return StockMovement.objects.create(
            material=self.mdf, movement_type=movement_type, quantity=Decimal(quantity), reason=reason
        )

    def test_balance_is_in_minus_out(self):
        self.move(MovementType.IN, "20")
        self.move(MovementType.OUT, "7.5", StockMovement.Reason.PRODUCTION)
        self.assertEqual(self.mdf.get_balance(), Decimal("12.5"))

    def test_out_more_than_balance_is_rejected(self):
        self.move(MovementType.IN, "3")
        with self.assertRaises(ValidationError):
            self.move(MovementType.OUT, "4", StockMovement.Reason.PRODUCTION)
        self.assertEqual(self.mdf.get_balance(), Decimal("3"))

    def test_low_stock(self):
        self.move(MovementType.IN, "10")
        self.assertFalse(Material.objects.low_stock().exists())
        self.move(MovementType.OUT, "6", StockMovement.Reason.PRODUCTION)
        self.assertIn(self.mdf, Material.objects.low_stock())  # 4 <= 5

    def test_movement_is_immutable(self):
        movement = self.move(MovementType.IN, "10")
        movement.quantity = Decimal("999")
        with self.assertRaises(ValidationError):
            movement.save()
