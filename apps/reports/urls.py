from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("finance/export/", views.finance_export, name="finance_export"),
]
