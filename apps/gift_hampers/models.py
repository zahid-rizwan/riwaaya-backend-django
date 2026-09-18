import uuid
from django.db import models
from apps.catalog.models import Product

class GiftHamper(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class HamperItem(models.Model):
    hamper = models.ForeignKey(
        GiftHamper, 
        on_delete=models.CASCADE, 
        related_name='items'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('hamper', 'product')

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in {self.hamper.name}"
