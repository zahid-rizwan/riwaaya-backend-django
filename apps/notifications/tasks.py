from config.celery import app
import logging

logger = logging.getLogger(__name__)

@app.task
def send_order_confirmation_email(order_id: str):
    logger.info(f"Sending order confirmation email for order {order_id} via Celery...")
    # Real email dispatch would be implemented here
    return True
