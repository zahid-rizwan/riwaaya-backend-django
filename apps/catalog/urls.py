from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.catalog.views import CategoryViewSet, ProductViewSet, SellerProductViewSet, AttributeViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'seller/products', SellerProductViewSet, basename='seller-product')
router.register(r'attributes', AttributeViewSet, basename='attribute')

urlpatterns = [
    path('', include(router.urls)),
]
