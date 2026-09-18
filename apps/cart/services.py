from django.db import transaction
from apps.cart.models import Cart, CartItem
from apps.catalog.models import Variant

def get_or_create_user_cart(user) -> Cart:
    """
    Service to get or create a cart for the user.
    """
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@transaction.atomic
def add_item_to_cart(user, variant: Variant, quantity: int = 1) -> CartItem:
    """
    Service to add an item to the user's cart.
    """
    cart = get_or_create_user_cart(user)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, variant=variant)
    
    if not created:
        cart_item.quantity += quantity
    else:
        cart_item.quantity = quantity
        
    cart_item.save()
    return cart_item


@transaction.atomic
def update_cart_item_quantity(user, variant: Variant, quantity: int) -> CartItem:
    """
    Service to update the quantity of a specific item in the cart.
    """
    cart = get_or_create_user_cart(user)
    if quantity <= 0:
        CartItem.objects.filter(cart=cart, variant=variant).delete()
        return None
        
    cart_item, _ = CartItem.objects.get_or_create(cart=cart, variant=variant)
    cart_item.quantity = quantity
    cart_item.save()
    return cart_item


@transaction.atomic
def remove_item_from_cart(user, variant: Variant):
    """
    Service to remove an item from the cart.
    """
    cart = get_or_create_user_cart(user)
    CartItem.objects.filter(cart=cart, variant=variant).delete()


@transaction.atomic
def clear_cart(cart: Cart):
    """
    Service to clear all items in a cart.
    """
    cart.items.all().delete()
