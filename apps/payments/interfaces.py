from abc import ABC, abstractmethod

class BasePaymentGateway(ABC):
    """
    Abstract Base Class for pluggable payment gateways.
    """
    @abstractmethod
    def initialize_payment(self, order_id: str, amount: float, currency: str = 'INR') -> dict:
        """
        Initializes a transaction with the payment gateway.
        Returns a dictionary with transaction metadata (e.g. order_id, key, token).
        """
        pass

    @abstractmethod
    def verify_payment(self, payload: dict, signature: str) -> bool:
        """
        Verifies the signature of a webhook or callback payload.
        """
        pass

    @abstractmethod
    def refund_payment(self, transaction_id: str, amount: float = None, reason: str = None) -> dict:
        """
        Processes a full or partial refund for a payment transaction.
        """
        pass
