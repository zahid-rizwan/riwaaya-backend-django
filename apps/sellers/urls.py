from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.sellers.views import SellerPublicViewSet, SellerMeView, SellerVerifyView, SellerAdminListView

router = DefaultRouter()
router.register(r'public', SellerPublicViewSet, basename='seller-public')

urlpatterns = [
    path('me/', SellerMeView.as_view(), name='seller_me'),
    path('admin/list/', SellerAdminListView.as_view(), name='seller_admin_list'),
    path('<uuid:pk>/verify/', SellerVerifyView.as_view(), name='seller_verify'),
    path('', include(router.urls)),
]
