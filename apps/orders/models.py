import uuid
from django.db import models
from django.conf import settings
from apps.catalog.models import Variant
from apps.coupons.models import Coupon

class OrderStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Payment'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    PACKED = 'PACKED', 'Packed'
    SHIPPED = 'SHIPPED', 'Shipped'
    DELIVERED = 'DELIVERED', 'Delivered'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    RETURNED = 'RETURNED', 'Returned'
    REFUNDED = 'REFUNDED', 'Refunded'


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='orders'
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING
    )
    shipping_address = models.JSONField(help_text="Snapshot of shipping address details")
    billing_address = models.JSONField(help_text="Snapshot of billing address details")
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    coupon = models.ForeignKey(
        Coupon, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='orders'
    )
    total_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.id} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE, 
        related_name='items'
    )
    variant = models.ForeignKey(
        Variant, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    # Snapshotted fields - MUST NEVER BE READ FROM Variant AFTER PURCHASE
    product_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100)
    variant_details = models.JSONField(help_text="Snapshot of variant attributes like Size, Color, Fabric")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.quantity} x {self.product_name} ({self.sku}) in Order {self.order.id}"
