from django.db import models
from apps.catalog.models import Variant

class Inventory(models.Model):
    variant = models.OneToOneField(
        Variant, 
        on_delete=models.CASCADE, 
        related_name='inventory'
    )
    available_stock = models.PositiveIntegerField(default=0)
    reserved_stock = models.PositiveIntegerField(default=0)
    damaged_stock = models.PositiveIntegerField(default=0)
    returned_stock = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "inventories"

    def __str__(self):
        return f"Stock for {self.variant.sku}: Avail={self.available_stock}, Res={self.reserved_stock}"
