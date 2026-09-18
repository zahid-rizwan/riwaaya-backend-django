from django.db import transaction
from apps.sellers.models import SellerProfile, VerificationStatus

@transaction.atomic
def verify_seller(seller_profile: SellerProfile, status: str, commission_percentage=None) -> SellerProfile:
    """
    Service for admin to verify (approve/reject) a seller and set their commission.
    """
    if status not in VerificationStatus.values:
        raise ValueError("Invalid verification status.")
        
    seller_profile.verification_status = status
    if commission_percentage is not None:
        seller_profile.commission_percentage = commission_percentage
        
    seller_profile.save()
    return seller_profile


@transaction.atomic
def update_seller_profile(seller_profile: SellerProfile, **fields) -> SellerProfile:
    """
    Service to update seller profile fields.
    """
    # Prevent updating user, verification_status or commission directly through here
    fields.pop('user', None)
    fields.pop('verification_status', None)
    fields.pop('commission_percentage', None)
    
    for field, value in fields.items():
        setattr(seller_profile, field, value)
        
    seller_profile.save()
    return seller_profile
