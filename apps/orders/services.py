from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

from apps.accounts.models import Address
from apps.cart.selectors import get_user_cart
from apps.cart.services import clear_cart
from apps.catalog.models import Variant
from apps.inventory.services import reserve_stock, release_stock, confirm_stock_sale
from apps.coupons.models import Coupon, DiscountType
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.payments.models import Payment, PaymentStatus
from apps.payments.razorpay_provider import RazorpayGateway

def get_payment_gateway():
    """
    Returns the configured pluggable payment gateway.
    """
    return RazorpayGateway()


@transaction.atomic
def create_order_from_cart(user, shipping_address_id: str, billing_address_id: str, coupon_code: str = None):
    """
    Service to place an order from the user's current shopping cart.
    Handles stock reservation, coupon calculations, and payment initialization.
    """
    cart = get_user_cart(user)
    cart_items = list(cart.items.all())
    
    if not cart_items:
        raise ValidationError("Cannot checkout an empty shopping cart.")

    # Validate addresses
    shipping_addr = Address.objects.get(pk=shipping_address_id, user=user)
    billing_addr = Address.objects.get(pk=billing_address_id, user=user)
    
    shipping_snapshot = {
        "recipient_name": shipping_addr.recipient_name,
        "phone_number": shipping_addr.phone_number,
        "street_address": shipping_addr.street_address,
        "city": shipping_addr.city,
        "state": shipping_addr.state,
        "postal_code": shipping_addr.postal_code,
        "country": shipping_addr.country
    }
    
    billing_snapshot = {
        "recipient_name": billing_addr.recipient_name,
        "phone_number": billing_addr.phone_number,
        "street_address": billing_addr.street_address,
        "city": billing_addr.city,
        "state": billing_addr.state,
        "postal_code": billing_addr.postal_code,
        "country": billing_addr.country
    }

    # Calculate base totals
    subtotal = Decimal('0.00')
    item_prices = {}  # Cache prices used for order items
    
    for item in cart_items:
        price = item.variant.discount_price if item.variant.discount_price else item.variant.price
        subtotal += price * item.quantity
        item_prices[item.id] = price

    # Apply Coupon
    coupon = None
    total_discount = Decimal('0.00')
    
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code, is_active=True)
            
            # Date checks
            now = timezone.now()
            if coupon.start_date > now or coupon.end_date < now:
                raise ValidationError("Coupon is expired or not yet active.")
                
            # Min order value check
            if subtotal < coupon.min_order_value:
                raise ValidationError(f"Minimum order value for coupon is {coupon.min_order_value}.")
                
            # Usage limit check
            if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
                raise ValidationError("Coupon usage limit exceeded.")
                
            # Discount calculation
            if coupon.discount_type == DiscountType.PERCENTAGE:
                discount_val = subtotal * (coupon.discount_value / Decimal('100.00'))
                if coupon.max_discount_value:
                    discount_val = min(discount_val, coupon.max_discount_value)
                total_discount = discount_val
            else:
                total_discount = min(coupon.discount_value, subtotal)
                
            coupon.used_count += 1
            coupon.save()
        except Coupon.DoesNotExist:
            raise ValidationError("Invalid coupon code.")

    shipping_cost = Decimal('150.00')  # Flat shipping rate
    tax = subtotal * Decimal('0.05')    # Flat 5% tax
    total_amount = subtotal + shipping_cost + tax - total_discount

    # Atomic stock reservation: Decrease available, increase reserved
    for item in cart_items:
        reserve_stock(item.variant, item.quantity)

    # Create Order object
    order = Order.objects.create(
        customer=user,
        status=OrderStatus.PENDING,
        shipping_address=shipping_snapshot,
        billing_address=billing_snapshot,
        shipping_cost=shipping_cost,
        tax=tax,
        coupon=coupon,
        total_discount=total_discount,
        subtotal=subtotal,
        total_amount=total_amount
    )

    # Create OrderItems snapshotting details
    for item in cart_items:
        # Resolve variant attributes into a simple key-value dict
        attributes = {}
        for link in item.variant.variant_attributes.all():
            val = link.attribute_value
            attributes[val.attribute.name] = val.value

        OrderItem.objects.create(
            order=order,
            variant=item.variant,
            product_name=item.variant.product.name,
            sku=item.variant.sku,
            variant_details=attributes,
            price=item_prices[item.id],
            quantity=item.quantity,
            discount=Decimal('0.00'),  # Individual item discounts can go here if needed
            tax=Decimal('0.00')
        )

    # Initialize payment gateway
    gateway = get_payment_gateway()
    payment_session = gateway.initialize_payment(order.id, total_amount)

    # Create local payment trace record
    Payment.objects.create(
        order=order,
        transaction_id=payment_session["id"],
        provider=payment_session["gateway"],
        amount=total_amount,
        status=PaymentStatus.PENDING,
        raw_response=payment_session
    )

    # Clear shopping cart items
    clear_cart(cart)

    return order, payment_session
