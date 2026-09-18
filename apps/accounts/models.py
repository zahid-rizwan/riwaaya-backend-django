import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

class UserRole(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
    ADMIN = 'ADMIN', 'Admin'
    SELLER = 'SELLER', 'Seller'
    CUSTOMER = 'CUSTOMER', 'Customer'
    WAREHOUSE = 'WAREHOUSE', 'Warehouse'
    SUPPORT = 'SUPPORT', 'Support'

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.role})"


class Address(models.Model):
    class AddressType(models.TextChoices):
        SHIPPING = 'SHIPPING', 'Shipping Address'
        BILLING = 'BILLING', 'Billing Address'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(
        max_length=10,
        choices=AddressType.choices,
        default=AddressType.SHIPPING
    )
    is_default = models.BooleanField(default=False)
    recipient_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    street_address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "addresses"

    def __str__(self):
        return f"{self.recipient_name} - {self.city}, {self.country}"
