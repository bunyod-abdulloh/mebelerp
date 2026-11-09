from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from apps.core.choices import Currency
from apps.customers.models import Customer
from apps.finance.models import Expense, Payment
from apps.orders.models import Order, OrderItem
from . import services
from .excel import build_finance_workbook

User = get_user_model()


class ReportsTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        # Ataylab formula ko'rinishidagi ism: Excel injection testi uchun
        customer = Customer.objects.create(name="=1+1", phone="+998901234567")
        deadline = self.today + timedelta(days=10)

        order = Order.objects.create(customer=customer, deadline=deadline)
        OrderItem.objects.create(order=order, name="Shkaf", unit_price=Decimal("1000000"))
        Payment.objects.create(order=order, amount=Decimal("400000"))
        Payment.objects.create(
            order=order, amount=Decimal("10"), currency=Currency.USD, usd_rate=Decimal("12000")
        )  # 120 000 so'mlik ekvivalent, lekin kassaga 10 USD tushgan

        cancelled = Order.objects.create(customer=customer, deadline=deadline)
        OrderItem.objects.create(order=cancelled, name="Stol", unit_price=Decimal("500000"))
        cancelled.change_status(Order.Status.CANCELLED)

        Expense.objects.create(category=Expense.Category.FOOD, amount=Decimal("150000"))
        Expense.objects.create(
            category=Expense.Category.TRANSPORT, amount=Decimal("5"), currency=Currency.USD
        )

    def test_summary_is_per_currency_without_conversion(self):
        s = services.period_summary(self.today, self.today)
        self.assertEqual(s["UZS"]["net"], Decimal("250000"))  # 400 000 - 150 000
        self.assertEqual(s["USD"]["net"], Decimal("5"))  # 10 - 5

    def test_cancelled_orders_are_not_debt(self):
        rows = services.debt_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["debt"], Decimal("480000"))  # 1 000 000 - 400 000 - 120 000

    def test_dashboard(self):
        data = services.dashboard_data(self.today)
        self.assertEqual(data["total_debt"], {"UZS": Decimal("480000")})
        self.assertEqual(data["orders_today"], 1)  # bekor qilingani sanalmaydi
        self.assertEqual(data["orders_by_status"]["cancelled"], 1)

    def test_excel_text_is_never_a_formula(self):
        wb = load_workbook(BytesIO(build_finance_workbook(self.today, self.today)))
        cell = wb["Tushumlar"].cell(row=2, column=3)  # Mijoz ustuni
        self.assertEqual(cell.value, "=1+1")
        self.assertEqual(cell.data_type, "s")

    def test_export_permissions(self):
        url = reverse("reports:finance_export")
        self.assertEqual(self.client.get(url).status_code, 302)  # login'ga yo'naltiradi

        worker = User.objects.create_user("worker", password="x", role=User.Role.WORKER)
        self.client.force_login(worker)
        self.assertEqual(self.client.get(url).status_code, 403)

        owner = User.objects.create_user("boss", password="x", role=User.Role.OWNER)
        self.client.force_login(owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])
