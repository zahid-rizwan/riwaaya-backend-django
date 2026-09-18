from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.orders.views import OrderViewSet, SellerOrderListView

router = DefaultRouter()
router.register(r'', OrderViewSet, basename='order')

urlpatterns = [
    path('seller/', SellerOrderListView.as_view(), name='seller_orders'),
    path('', include(router.urls)),
]
