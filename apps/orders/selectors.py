from django.db.models import QuerySet
from apps.orders.models import Order
from apps.sellers.models import SellerProfile

def get_user_orders(user) -> QuerySet:
    """
    Selector to retrieve orders belonging to a customer.
    """
    return Order.objects.filter(customer=user).prefetch_related(
        'items__variant__product__seller',
        'payments'
    ).order_by('-created_at')


def get_order_by_id(user, order_id: str) -> Order:
    """
    Selector to retrieve a specific order for a customer.
    """
    return Order.objects.prefetch_related(
        'items__variant__product__seller',
        'payments'
    ).get(pk=order_id, customer=user)


def get_seller_orders(seller: SellerProfile) -> QuerySet:
    """
    Selector to retrieve orders that contain at least one item from the given seller.
    """
    return Order.objects.filter(
        items__variant__product__seller=seller
    ).distinct().prefetch_related(
        'items__variant__product__seller',
        'payments'
    ).order_by('-created_at')
