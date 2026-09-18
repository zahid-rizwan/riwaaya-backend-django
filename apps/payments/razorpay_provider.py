import razorpay
from django.conf import settings
from apps.payments.interfaces import BasePaymentGateway

class RazorpayGateway(BasePaymentGateway):
    def __init__(self):
        self.key_id = getattr(settings, 'RAZORPAY_KEY_ID', 'mock_key_id')
        self.key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', 'mock_key_secret')
        self.is_mock = self.key_id == 'mock_key_id' or self.key_secret == 'mock_key_secret'
        
        if not self.is_mock:
            self.client = razorpay.Client(auth=(self.key_id, self.key_secret))

    def initialize_payment(self, order_id: str, amount: float, currency: str = 'INR') -> dict:
        # Razorpay works in subunits (paise for INR)
        amount_paise = int(amount * 100)
        
        if self.is_mock:
            return {
                "gateway": "razorpay",
                "id": f"order_mock_{order_id}",
                "amount": amount_paise,
                "currency": currency,
                "key": self.key_id
            }
            
        try:
            razorpay_order = self.client.order.create(data={
                "amount": amount_paise,
                "currency": currency,
                "receipt": str(order_id),
                "payment_capture": 1
            })
            return {
                "gateway": "razorpay",
                "id": razorpay_order["id"],
                "amount": razorpay_order["amount"],
                "currency": razorpay_order["currency"],
                "key": self.key_id
            }
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Razorpay order: {e}")

    def verify_payment(self, payload: dict, signature: str) -> bool:
        if self.is_mock:
            return True
            
        try:
            self.client.utility.verify_payment_signature({
                'razorpay_order_id': payload.get('razorpay_order_id'),
                'razorpay_payment_id': payload.get('razorpay_payment_id'),
                'razorpay_signature': signature
            })
            return True
        except Exception:
            return False

    def refund_payment(self, transaction_id: str, amount: float = None, reason: str = None) -> dict:
        if self.is_mock:
            return {
                "status": "refunded", 
                "id": f"rfnd_mock_{transaction_id}", 
                "amount": amount
            }
            
        data = {}
        if amount is not None:
            data["amount"] = int(amount * 100)
            
        try:
            refund = self.client.refund.create(payment_id=transaction_id, data=data)
            return {
                "status": refund.get("status"),
                "id": refund.get("id"),
                "amount": float(refund.get("amount", 0)) / 100.0
            }
        except Exception as e:
            raise RuntimeError(f"Failed to process refund: {e}")
