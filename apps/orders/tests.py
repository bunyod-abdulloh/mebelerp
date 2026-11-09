from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.customers.models import Customer
from .models import Order, OrderItem


class OrderWorkflowTests(TestCase):
    def setUp(self):
        customer = Customer.objects.create(name="Ali", phone="+998901234567")
        self.order = Order.objects.create(
            customer=customer, deadline=timezone.localdate() + timedelta(days=10)
        )
        OrderItem.objects.create(order=self.order, name="Shkaf", unit_price=1000)

    def test_valid_flow_writes_history(self):
        self.order.change_status(Order.Status.IN_PRODUCTION)
        self.order.change_status(Order.Status.READY)
        self.assertEqual(self.order.status_history.count(), 2)

    def test_invalid_transition_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.order.change_status(Order.Status.DELIVERED)  # new -> delivered mumkin emas

    def test_items_locked_after_delivery(self):
        for s in (Order.Status.IN_PRODUCTION, Order.Status.READY, Order.Status.DELIVERED):
            self.order.change_status(s)
        with self.assertRaises(ValidationError):
            OrderItem.objects.create(order=self.order, name="Qo'shimcha", unit_price=1)
