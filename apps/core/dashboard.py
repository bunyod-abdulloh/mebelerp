import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.core.choices import Currency
from apps.core.formatting import format_money
from apps.finance.models import Expense, Payment
from apps.orders.models import Order

ZERO = Decimal("0")
MONTHS_UZ = ["Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek"]
INCOME_COLOR = "var(--color-primary-600)"
EXPENSE_COLOR = "#ef4444"


def _month_start(today, offset=0):
    index = today.month - 1 + offset
    return date(today.year + index // 12, index % 12 + 1, 1)


def _monthly_sum(queryset, date_field, amount_field):
    rows = (
        queryset.annotate(month=TruncMonth(date_field))
        .values("month").order_by("month")
        .annotate(total=Sum(amount_field))
    )
    return {(r["month"].year, r["month"].month): r["total"] for r in rows}


def _days_left(deadline, today):
    days = (deadline - today).days
    if days > 0:
        return f"{days} kun"
    return "Bugun" if days == 0 else f"{-days} kun kechikdi"


def _bar(labels, datasets):
    return json.dumps({"labels": labels, "datasets": datasets})


def dashboard_callback(request, context):
    today = timezone.localdate()
    months = [_month_start(today, -i) for i in range(5, -1, -1)]
    current = months[-1]
    current_key = (current.year, current.month)

    income = _monthly_sum(
        Payment.objects.filter(order__currency=Currency.UZS, paid_at__date__gte=months[0]),
        "paid_at", "order_amount",
    )
    expense = _monthly_sum(
        Expense.objects.filter(currency=Currency.UZS, date__gte=months[0]),
        "date", "amount",
    )
    month_income = income.get(current_key, ZERO)
    month_expense = expense.get(current_key, ZERO)

    def series(data):
        return [float(data.get((m.year, m.month), ZERO)) for m in months]

    # Qarz: bitta so'rov, qolganini Python'da hisoblaymiz
    debt_orders = list(
        Order.objects.with_debt().filter(currency=Currency.UZS).select_related("customer")
    )
    total_debt = sum((o.debt for o in debt_orders), ZERO)
    overdue = sorted(
        (o for o in debt_orders if o.payment_due_date and o.payment_due_date < today),
        key=lambda o: o.payment_due_date,
    )
    by_customer = defaultdict(lambda: [None, ZERO])
    for o in debt_orders:
        entry = by_customer[o.customer_id]
        entry[0] = o.customer.name
        entry[1] += o.debt
    top_debtors = sorted(by_customer.values(), key=lambda e: e[1], reverse=True)[:5]

    # Xarajatlar kategoriya bo'yicha (joriy oy)
    category_labels = dict(Expense.Category.choices)
    categories = list(
        Expense.objects.filter(currency=Currency.UZS, date__gte=current)
        .values("category").order_by().annotate(total=Sum("amount")).order_by("-total")
    )

    # Faol buyurtmalar holati
    status_labels = dict(Order.Status.choices)
    status_counts = dict(
        Order.objects.exclude(status__in=Order.FINAL_STATUSES)
        .values_list("status").order_by().annotate(c=Count("id"))
    )
    active_statuses = [s for s in Order.Status.values if s not in Order.FINAL_STATUSES]

    upcoming = (
        Order.objects.exclude(status__in=Order.FINAL_STATUSES)
        .filter(deadline__lte=today + timedelta(days=7))
        .select_related("customer").order_by("deadline")[:5]
    )

    context.update({
        "month_income": format_money(month_income),
        "month_expense": format_money(month_expense),
        "month_net": format_money(month_income - month_expense),
        "total_debt": format_money(total_debt),
        "overdue_count": len(overdue),
        "active_count": sum(status_counts.values()),
        "cashflow_chart": _bar(
            [f"{MONTHS_UZ[m.month - 1]} {m.year}" for m in months],
            [
                {"label": "Tushum", "data": series(income), "backgroundColor": INCOME_COLOR},
                {"label": "Xarajat", "data": series(expense), "backgroundColor": EXPENSE_COLOR},
            ],
        ),
        "expense_chart": _bar(
            [category_labels.get(c["category"], c["category"]) for c in categories],
            [{"label": "Xarajat (UZS)", "data": [float(c["total"]) for c in categories],
              "backgroundColor": EXPENSE_COLOR}],
        ),
        "status_chart": _bar(
            [status_labels[s] for s in active_statuses],
            [{"label": "Buyurtmalar", "data": [status_counts.get(s, 0) for s in active_statuses],
              "backgroundColor": INCOME_COLOR}],
        ),
        "overdue_table": {
            "headers": ["Buyurtma raqami", "Mijoz", "To'lov muddati", "Qarz"],
            "rows": [
                [o.number, o.customer.name, o.payment_due_date.strftime("%d.%m.%Y"),
                 f"{format_money(o.debt)} {o.currency}"]
                for o in overdue[:5]
            ],
        },
        "debtors_table": {
            "headers": ["Mijoz", "Qarz (UZS)"],
            "rows": [[name, format_money(amount)] for name, amount in top_debtors],
        },
        "upcoming_table": {
            "headers": ["Buyurtma raqami", "Mijoz", "Topshirish", "Qoldi", "Holat"],
            "rows": [
                [o.number, o.customer.name, o.deadline.strftime("%d.%m.%Y"),
                 _days_left(o.deadline, today), o.get_status_display()]
                for o in upcoming
            ],
        },
    })
    return context
