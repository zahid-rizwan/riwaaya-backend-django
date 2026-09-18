from django.db import transaction
from django.contrib.auth import get_user_model
from apps.accounts.models import Address, UserRole
from apps.sellers.models import SellerProfile

User = get_user_model()

@transaction.atomic
def register_customer(username, email, password, phone_number=None):
    """
    Service to register a new customer user.
    """
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        role=UserRole.CUSTOMER,
        phone_number=phone_number
    )
    return user


@transaction.atomic
def register_seller(
    username, email, password, 
    business_name, gst_number, pan, 
    business_address, pickup_address, 
    contact_phone, contact_email, 
    bank_details=None
):
    """
    Service to register a new seller and their seller profile in a single atomic transaction.
    """
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        role=UserRole.SELLER,
        phone_number=contact_phone
    )
    
    profile = SellerProfile.objects.create(
        user=user,
        business_name=business_name,
        gst_number=gst_number,
        pan=pan,
        business_address=business_address,
        pickup_address=pickup_address,
        bank_details=bank_details or {},
        contact_phone=contact_phone,
        contact_email=contact_email
    )
    
    return user, profile


@transaction.atomic
def create_address(user, address_type, recipient_name, phone_number, street_address, city, state, postal_code, country, is_default=False):
    """
    Service to create a new address. If is_default is True, we unset any existing default address of the same type.
    """
    if is_default:
        Address.objects.filter(user=user, address_type=address_type, is_default=True).update(is_default=False)
        
    address = Address.objects.create(
        user=user,
        address_type=address_type,
        is_default=is_default,
        recipient_name=recipient_name,
        phone_number=phone_number,
        street_address=street_address,
        city=city,
        state=state,
        postal_code=postal_code,
        country=country
    )
    return address


@transaction.atomic
def update_address(address, **fields):
    """
    Service to update an address and enforce the default address constraint.
    """
    is_default = fields.get('is_default', address.is_default)
    address_type = fields.get('address_type', address.address_type)
    
    if is_default and (not address.is_default or address_type != address.address_type):
        Address.objects.filter(user=address.user, address_type=address_type, is_default=True).update(is_default=False)
        
    for field, value in fields.items():
        setattr(address, field, value)
        
    address.save()
    return address
