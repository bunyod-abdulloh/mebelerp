from decimal import Decimal
from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from . import services


def _append(ws, values):
    ws.append(values)
    for cell in ws[ws.max_row]:
        if cell.data_type == "f":
            cell.data_type = "s"  # foydalanuvchi matni hech qachon formula bo'lmasin
        elif isinstance(cell.value, Decimal):
            cell.number_format = "#,##0.00"


def _sheet(wb, title, header, rows, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    ws.append(header)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        _append(ws, row)
    ws.freeze_panes = "A2"
    for idx, name in enumerate(header, 1):
        ws.column_dimensions[get_column_letter(idx)].width = max(16, len(name) + 4)


def _local(dt):
    return timezone.localtime(dt).replace(tzinfo=None)


def build_finance_workbook(date_from, date_to) -> bytes:
    wb = Workbook()

    summary = services.period_summary(date_from, date_to)
    _sheet(wb, "Xulosa", ["Valyuta", "Tushum", "Chiqim", "Farq"],
           [[cur, v["income"], v["expense"], v["net"]] for cur, v in summary.items()], first=True)

    payments = payments_in_period(date_from, date_to)
    _sheet(wb, "Tushumlar", ["Sana", "Buyurtma", "Mijoz", "Usul", "Summa", "Valyuta", "Izoh"], [
        [_local(p.paid_at), p.order.number, p.order.customer.name,
         p.get_method_display(), p.amount, p.currency, p.note]
        for p in payments
    ])

    expenses = services.expenses_in(date_from, date_to).order_by("date", "id")
    _sheet(wb, "Chiqimlar", ["Sana", "Toifa", "Summa", "Valyuta", "To'lov turi", "Izoh"], [
        [e.date, e.get_category_display(), e.amount, e.currency, e.get_method_display(), e.note]
        for e in expenses
    ])

    _sheet(wb, "Qarzdorlar",
           ["Buyurtma", "Mijoz", "Telefon", "Valyuta", "Jami", "To'langan", "Qarz", "To'lov muddati"], [
               [services.order_number(r["id"]), r["customer__name"], r["customer__phone"], r["currency"],
                r["total"], r["paid"], r["debt"], r["payment_due_date"]]
               for r in services.debt_rows()
           ])

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def payments_in_period(date_from, date_to):
    return (
        services.payments_in(date_from, date_to)
        .select_related("order__customer").order_by("paid_at")  # N+1 yo'q
    )
