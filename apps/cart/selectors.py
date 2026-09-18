from apps.cart.models import Cart

def get_user_cart(user) -> Cart:
    """
    Selector to retrieve user cart with pre-fetched items and variants.
    """
    try:
        return Cart.objects.prefetch_related(
            'items__variant__product__seller',
            'items__variant__variant_attributes__attribute_value__attribute',
            'items__variant__images'
        ).get(user=user)
    except Cart.DoesNotExist:
        # Create it lazily
        from apps.cart.services import get_or_create_user_cart
        return get_or_create_user_cart(user)
