from django.db.models import QuerySet
from apps.sellers.models import SellerProfile, VerificationStatus

def get_active_sellers() -> QuerySet:
    """
    Selector to retrieve only verified/active sellers.
    """
    return SellerProfile.objects.filter(verification_status=VerificationStatus.APPROVED)


def get_seller_profile_by_user(user) -> SellerProfile:
    """
    Selector to retrieve a seller's profile by their user.
    """
    return SellerProfile.objects.select_related('user').get(user=user)
