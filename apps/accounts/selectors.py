from apps.accounts.models import Address

def get_user_addresses(user, address_type=None):
    """
    Selector to retrieve user addresses.
    """
    queryset = Address.objects.filter(user=user)
    if address_type:
        queryset = queryset.filter(address_type=address_type)
    return queryset.order_list('-is_default', '-created_at') if hasattr(queryset, 'order_list') else queryset.order_by('-is_default', '-created_at')
