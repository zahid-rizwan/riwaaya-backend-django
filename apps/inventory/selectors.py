from apps.catalog.models import Variant
from apps.inventory.models import Inventory

def get_variant_stock(variant: Variant) -> Inventory:
    """
    Selector to retrieve stock details for a variant.
    """
    inventory, _ = Inventory.objects.get_or_create(variant=variant)
    return inventory
