from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET

from apps.products.models import Product


@method_decorator(require_GET)
def product_data_view(self, request):
    if not request.user.has_perm("products.view_product"):
        raise PermissionDenied
    try:
        pk = int(request.GET.get("product", ""))
    except ValueError:
        return JsonResponse({"error": "invalid product"}, status=400)

    product = get_object_or_404(Product, pk=pk, is_active=True)
    return JsonResponse({
        "name": product.name,
        "unit": product.unit,
        "unit_price": str(product.price),
        "currency": product.currency,
    })