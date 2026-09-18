import uuid
from django.db import models
from apps.sellers.models import SellerProfile
from apps.catalog.models import Category, Product

class DiscountType(models.TextChoices):
    PERCENTAGE = 'PERCENTAGE', 'Percentage'
    FLAT = 'FLAT', 'Flat Amount'

class Coupon(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.FLAT
    )
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    seller = models.ForeignKey(
        SellerProfile, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='coupons',
        help_text="Null indicates platform-wide coupon"
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='coupons'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='coupons'
    )
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    max_discount_value = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    free_shipping = models.BooleanField(default=False)
    usage_limit = models.PositiveIntegerField(blank=True, null=True)
    used_count = models.PositiveIntegerField(default=0)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} ({self.discount_type}: {self.discount_value})"
