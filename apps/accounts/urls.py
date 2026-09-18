from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.accounts.views import (
    CustomerRegisterView, 
    SellerRegisterView, 
    UserMeView, 
    AddressViewSet
)

router = DefaultRouter()
router.register(r'addresses', AddressViewSet, basename='address')

urlpatterns = [
    # JWT authentication endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Registration endpoints
    path('register/customer/', CustomerRegisterView.as_view(), name='register_customer'),
    path('register/seller/', SellerRegisterView.as_view(), name='register_seller'),
    
    # Profile endpoint
    path('me/', UserMeView.as_view(), name='user_me'),
    
    # Address Viewset urls
    path('', include(router.urls)),
]
