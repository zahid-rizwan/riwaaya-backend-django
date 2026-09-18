from django.db import models


class GuestCart(models.Model):
    session_id = models.CharField(max_length=255, unique=True)
    items = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.session_id