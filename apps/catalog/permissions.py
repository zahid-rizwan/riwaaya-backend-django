from rest_framework import permissions
from apps.accounts.models import UserRole

class IsSellerOrAdmin(permissions.BasePermission):
    """
    Allows Sellers (for their own products) and Admins/SuperAdmins (for all products) to manage products.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role in (UserRole.SELLER, UserRole.ADMIN, UserRole.SUPER_ADMIN)
        )

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
            return True
        if request.user.role == UserRole.SELLER:
            return hasattr(request.user, 'seller_profile') and obj.seller == request.user.seller_profile
        return False
