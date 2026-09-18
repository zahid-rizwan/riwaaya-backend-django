from django.urls import path
from apps.payments.views import RazorpayWebhookView

urlpatterns = [
    path('webhook/', RazorpayWebhookView.as_view(), name='razorpay_webhook'),
]
