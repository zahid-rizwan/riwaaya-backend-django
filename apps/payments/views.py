import logging
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.payments.services import fulfill_payment, fail_payment

logger = logging.getLogger(__name__)

class RazorpayWebhookView(APIView):
    """
    Webhook receiver endpoint for Razorpay payment callback events.
    """
    permission_classes = (permissions.AllowAny,)

    @extend_schema(summary="Razorpay Webhook receiver", exclude=True)
    def post(self, request, *args, **kwargs):
        payload = request.data
        signature = request.headers.get('X-Razorpay-Signature', '')
        
        event = payload.get('event')
        payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
        order_id = payment_entity.get('order_id')  # This matches the initialized payment transaction_id

        if not order_id:
            return Response({"error": "No order_id found in event payload"}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"Payment Webhook received event: {event} for order transaction: {order_id}")

        try:
            if event == 'payment.captured':
                fulfill_payment(
                    transaction_id=order_id,
                    gateway_payload=payload,
                    signature=signature
                )
                return Response({"status": "success"}, status=status.HTTP_200_OK)
                
            elif event in ('payment.failed', 'order.expired'):
                fail_payment(transaction_id=order_id)
                return Response({"status": "payment_failure_processed"}, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Error handling webhook event {event}: {e}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "ignored"}, status=status.HTTP_200_OK)
