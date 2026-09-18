import uuid
from django.db import models
from django.conf import settings

class VerificationStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'

class SellerProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seller_profile'
    )
    business_name = models.CharField(max_length=255)
    gst_number = models.CharField(max_length=15, unique=True)
    pan = models.CharField(max_length=10, unique=True)
    business_address = models.TextField()
    pickup_address = models.TextField()
    bank_details = models.JSONField(default=dict, help_text="Stores bank name, account number, IFSC, holder name")
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING
    )
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00
    )
    logo = models.ImageField(upload_to='seller_logos/', blank=True, null=True)
    contact_phone = models.CharField(max_length=20)
    contact_email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.business_name} ({self.verification_status})"
