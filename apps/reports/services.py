from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.utils import timezone

from apps.core.choices import Currency
from apps.finance.models import Expense, Payment
from apps.inventory.models import Material
from apps.orders.models import Order

ZERO = Decimal("0")


def day_bounds(date_from, date_to):
    """[date_from 00:00, date_to + 1 kun 00:00) oralig'i: index'ga mos filtr uchun."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date_from, time.min), tz)
    end = timezone.make_aware(datetime.combine(date_to + timedelta(days=1), time.min), tz)
    return start, end


def payments_in(date_from, date_to):
    start, end = day_bounds(date_from, date_to)
    return Payment.objects.filter(paid_at__gte=start, paid_at__lt=end)


def expenses_in(date_from, date_to):
    return Expense.objects.filter(date__gte=date_from, date__lte=date_to)


def period_summary(date_from, date_to):
    """{'UZS': {'income', 'expense', 'net'}, 'USD': {...}}: valyutalar aralashtirilmaydi."""
    income = dict(
        payments_in(date_from, date_to).values_list("currency").annotate(t=Sum("amount")).order_by()
    )
    spent = dict(
        expenses_in(date_from, date_to).values_list("currency").annotate(t=Sum("amount")).order_by()
    )
    summary = {}
    for currency in Currency.values:
        i, e = income.get(currency, ZERO), spent.get(currency, ZERO)
        summary[currency] = {"income": i, "expense": e, "net": i - e}
    return summary


def income_by_method(date_from, date_to):
    return list(
        payments_in(date_from, date_to).values("method", "currency")
        .annotate(total=Sum("amount")).order_by("method", "currency")
    )


def expense_by_category(date_from, date_to):
    return list(
        expenses_in(date_from, date_to).values("category", "currency")
        .annotate(total=Sum("amount")).order_by("category", "currency")
    )


def debt_rows():
    """Qarzi bor buyurtmalar (bekor qilinganlarsiz): muddati o'tganlar birinchi."""
    return list(
        Order.objects.with_debt()
        .values("id", "customer__name", "customer__phone", "currency",
                "total", "paid", "debt", "payment_due_date")
        .order_by(F("payment_due_date").asc(nulls_last=True), "id")
    )


def dashboard_data(today=None):
    today = today or timezone.localdate()
    month_start = today.replace(day=1)
    active = Order.objects.exclude(status=Order.Status.CANCELLED)

    total_debt = {}
    for row in debt_rows():
        total_debt[row["currency"]] = total_debt.get(row["currency"], ZERO) + row["debt"]

    return {
        "orders_today": active.filter(order_date=today).count(),
        "orders_month": active.filter(order_date__gte=month_start, order_date__lte=today).count(),
        "orders_by_status": dict(
            Order.objects.values_list("status").annotate(c=Count("id")).order_by()
        ),
        "month": period_summary(month_start, today),
        "total_debt": total_debt,
        "overdue_count": Order.objects.overdue().count(),
        "low_stock": list(Material.objects.low_stock().values("name", "balance", "min_quantity")),
    }
