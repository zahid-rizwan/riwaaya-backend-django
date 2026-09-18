import uuid
from django.db import models
from django.conf import settings
from apps.catalog.models import Product
from apps.sellers.models import SellerProfile

class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='reviews'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='reviews'
    )
    seller = models.ForeignKey(
        SellerProfile, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='reviews'
    )
    rating = models.PositiveSmallIntegerField(
        help_text="Rating between 1 and 5 stars"
    )
    title = models.CharField(max_length=255)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        target = f"Product: {self.product.name}" if self.product else f"Seller: {self.seller.business_name}"
        return f"Review ({self.rating} stars) by {self.customer.username} for {target}"


class ReviewImage(models.Model):
    review = models.ForeignKey(
        Review, 
        on_delete=models.CASCADE, 
        related_name='images'
    )
    image = models.ImageField(upload_to='review_images/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for Review {self.review.id}"
