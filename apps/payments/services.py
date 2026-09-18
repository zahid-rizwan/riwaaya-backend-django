from django.db import transaction
from django.core.exceptions import ValidationError
from apps.payments.models import Payment, PaymentStatus
from apps.orders.models import Order, OrderStatus
from apps.inventory.services import confirm_stock_sale, release_stock
from apps.payments.razorpay_provider import RazorpayGateway

def get_payment_gateway():
    return RazorpayGateway()


@transaction.atomic
def fulfill_payment(transaction_id: str, gateway_payload: dict, signature: str) -> Payment:
    """
    Fulfills an order after verifying payment success.
    Moves inventory from reserved to sold.
    """
    try:
        payment = Payment.objects.select_for_update().get(transaction_id=transaction_id)
    except Payment.DoesNotExist:
        raise ValidationError(f"Payment with transaction ID {transaction_id} not found.")

    if payment.status == PaymentStatus.SUCCESS:
        return payment  # Already processed

    gateway = get_payment_gateway()
    if not gateway.verify_payment(gateway_payload, signature):
        raise ValidationError("Payment signature verification failed.")

    # Update Payment status
    payment.status = PaymentStatus.SUCCESS
    payment.raw_response = {**payment.raw_response, "callback_payload": gateway_payload}
    payment.save()

    # Update Order status
    order = payment.order
    order.status = OrderStatus.CONFIRMED
    order.save()

    # Confirm stock sale: decrement reserved stock
    for item in order.items.all():
        if item.variant:
            confirm_stock_sale(item.variant, item.quantity)

    # Trigger async notifications via celery (to be implemented in notifications task)
    from apps.notifications.tasks import send_order_confirmation_email
    transaction.on_commit(lambda: send_order_confirmation_email.delay(str(order.id)))

    return payment


@transaction.atomic
def fail_payment(transaction_id: str) -> Payment:
    """
    Handles payment failure or order cancellation.
    Reverts inventory from reserved back to available, and refunds coupon usage.
    """
    try:
        payment = Payment.objects.select_for_update().get(transaction_id=transaction_id)
    except Payment.DoesNotExist:
        raise ValidationError(f"Payment with transaction ID {transaction_id} not found.")

    if payment.status in (PaymentStatus.SUCCESS, PaymentStatus.FAILURE):
        return payment  # Already processed

    # Update Payment status
    payment.status = PaymentStatus.FAILURE
    payment.save()

    # Update Order status
    order = payment.order
    order.status = OrderStatus.CANCELLED
    order.save()

    # Revert inventory: reserved stock decreases, available increases
    for item in order.items.all():
        if item.variant:
            release_stock(item.variant, item.quantity)

    # Revert coupon use count if applicable
    if order.coupon:
        coupon = order.coupon
        if coupon.used_count > 0:
            coupon.used_count -= 1
            coupon.save()

    return payment
