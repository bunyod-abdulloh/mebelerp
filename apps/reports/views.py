from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.core.permissions import owner_required
from .excel import build_finance_workbook
from .forms import PeriodForm

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@owner_required
@require_GET
def finance_export(request):
    today = timezone.localdate()
    # Parametr berilmasa: joriy oy
    form = PeriodForm(request.GET or {"date_from": today.replace(day=1), "date_to": today})
    if not form.is_valid():
        return HttpResponse(form.errors.as_text(), status=400, content_type="text/plain; charset=utf-8")

    date_from, date_to = form.cleaned_data["date_from"], form.cleaned_data["date_to"]
    response = HttpResponse(build_finance_workbook(date_from, date_to), content_type=XLSX)
    # Fayl nomi tekshirilgan sanalardan yasaladi: header injection imkoni yo'q
    response["Content-Disposition"] = f'attachment; filename="finance_{date_from:%Y%m%d}_{date_to:%Y%m%d}.xlsx"'
    return response
