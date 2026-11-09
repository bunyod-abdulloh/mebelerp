from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from apps.core.choices import Currency
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from .models import ExchangeRate, Payment, Expense


class PaymentTests(TestCase):
    def setUp(self):
        customer = Customer.objects.create(name="Ali", phone="+998901234567")
        self.order = Order.objects.create(
            customer=customer, discount=Decimal("100000"),
            deadline=timezone.localdate() + timedelta(days=14),
        )
        OrderItem.objects.create(order=self.order, name="Oshxona", quantity=2, unit_price=Decimal("1000000"))
        OrderItem.objects.create(order=self.order, name="Stol", quantity=1, unit_price=Decimal("500000"))

    def pay(self, amount, currency=Currency.UZS, usd_rate=None):
        return Payment.objects.create(
            order=self.order, amount=Decimal(amount), currency=currency, usd_rate=usd_rate
        )

    def totals(self):
        return Order.objects.with_totals().get(pk=self.order.pk)

    def test_totals_are_not_multiplied_by_joins(self):
        self.pay("500000")
        self.pay("300000")  # 2 ta pozitsiya x 2 ta to'lov: JOIN xatosini ushlaydi
        o = self.totals()
        self.assertEqual(o.total, Decimal("2400000"))  # 2 500 000 - 100 000
        self.assertEqual(o.paid, Decimal("800000"))
        self.assertEqual(o.debt, Decimal("1600000"))

    def test_usd_payment_is_converted_and_rate_saved(self):
        p = self.pay("40", Currency.USD, usd_rate=Decimal("12500"))
        self.assertEqual(p.order_amount, Decimal("500000.00"))
        self.assertEqual(self.totals().debt, Decimal("1900000"))

    def test_latest_exchange_rate_is_used_when_not_given(self):
        ExchangeRate.objects.create(date=timezone.localdate(), usd_to_uzs=Decimal("12000"))
        p = self.pay("10", Currency.USD)
        self.assertEqual(p.usd_rate, Decimal("12000"))
        self.assertEqual(p.order_amount, Decimal("120000.00"))

    def test_rate_required_for_foreign_currency(self):
        with self.assertRaises(ValidationError):
            self.pay("10", Currency.USD)

    def test_overpayment_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.pay("2400001")
        self.assertEqual(self.totals().paid, Decimal("0"))

    def test_order_with_payments_cannot_be_cancelled(self):
        self.pay("100000")
        with self.assertRaises(ValidationError):
            self.order.change_status(Order.Status.CANCELLED)

    def test_payment_is_immutable(self):
        p = self.pay("100000")
        p.amount = Decimal("1")
        with self.assertRaises(ValidationError):
            p.save()


class ExpenseTests(TestCase):
    def test_amount_must_be_positive(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError), transaction.atomic():
            Expense.objects.create(category=Expense.Category.FOOD, amount=Decimal("0"))

    def test_only_safe_document_types_allowed(self):
        expense = Expense(
            category=Expense.Category.OTHER, amount=Decimal("1000"),
            document=SimpleUploadedFile("virus.exe", b"MZ"),
        )
        with self.assertRaises(ValidationError):
            expense.full_clean()
