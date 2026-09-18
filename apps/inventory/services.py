from django.db import transaction
from django.core.exceptions import ValidationError
from apps.catalog.models import Variant
from apps.inventory.models import Inventory

@transaction.atomic
def reserve_stock(variant: Variant, quantity: int) -> Inventory:
    """
    Reserves stock for a variant when checkout starts.
    Decreases available_stock and increases reserved_stock.
    Locks the row to prevent concurrent race conditions.
    """
    # Get or create inventory for safety, lock the row
    inventory, _ = Inventory.objects.select_for_update().get_or_create(variant=variant)
    
    if inventory.available_stock < quantity:
        raise ValidationError(
            f"Insufficient stock for SKU {variant.sku}. "
            f"Available: {inventory.available_stock}, requested: {quantity}"
        )
        
    inventory.available_stock -= quantity
    inventory.reserved_stock += quantity
    inventory.save()
    return inventory


@transaction.atomic
def release_stock(variant: Variant, quantity: int) -> Inventory:
    """
    Releases previously reserved stock back to available (e.g. payment failed or checkout expired).
    Decreases reserved_stock and increases available_stock.
    """
    inventory, _ = Inventory.objects.select_for_update().get_or_create(variant=variant)
    
    # Adjust quantity to prevent negative reserved stock
    release_qty = min(inventory.reserved_stock, quantity)
    
    inventory.reserved_stock -= release_qty
    inventory.available_stock += release_qty
    inventory.save()
    return inventory


@transaction.atomic
def confirm_stock_sale(variant: Variant, quantity: int) -> Inventory:
    """
    Finalizes sales after successful payment.
    Decreases reserved_stock.
    """
    inventory, _ = Inventory.objects.select_for_update().get_or_create(variant=variant)
    
    sale_qty = min(inventory.reserved_stock, quantity)
    inventory.reserved_stock -= sale_qty
    inventory.save()
    return inventory


@transaction.atomic
def replenish_stock(variant: Variant, quantity: int) -> Inventory:
    """
    Adds new inventory stock for a variant.
    """
    inventory, _ = Inventory.objects.select_for_update().get_or_create(variant=variant)
    inventory.available_stock += quantity
    inventory.save()
    return inventory
