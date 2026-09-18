from rest_framework import viewsets, permissions, status, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema

from apps.accounts.models import UserRole
from apps.accounts.permissions import IsSeller
from apps.catalog.permissions import IsSellerOrAdmin
from apps.catalog.models import Category, Product, Variant, Attribute, AttributeValue
from apps.catalog.serializers import (
    CategorySerializer, 
    ProductSerializer, 
    ProductCreateSerializer,
    VariantSerializer, 
    VariantCreateSerializer,
    AttributeSerializer
)
from apps.catalog.selectors import (
    get_active_products, 
    get_product_by_slug, 
    get_categories, 
    get_products_in_category
)

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint to list and view categories.
    """
    queryset = get_categories()
    serializer_class = CategorySerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = 'slug'

    @extend_schema(summary="List categories")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Retrieve category details by slug")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['get'], url_path='products')
    @extend_schema(summary="Get all products in this category (and subcategories)")
    def products(self, request, slug=None):
        queryset = get_products_in_category(slug)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProductSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ProductSerializer(queryset, many=True)
        return Response(serializer.data)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint to list and retrieve products. Open to the public.
    """
    queryset = get_active_products()
    serializer_class = ProductSerializer
    permission_classes = (permissions.AllowAny,)
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_fields = ('category__slug', 'seller__id')
    search_fields = ('name', 'description')
    ordering_fields = ('created_at',)
    lookup_field = 'slug'

    @extend_schema(summary="List and search products")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Retrieve product detail by slug")
    def retrieve(self, request, *args, **kwargs):
        slug = kwargs.get('slug')
        product = get_product_by_slug(slug)
        serializer = self.get_serializer(product)
        return Response(serializer.data)


class SellerProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint for sellers and admins to manage products.
    """
    serializer_class = ProductSerializer
    permission_classes = (IsSellerOrAdmin,)

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Product.objects.none()
        if user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
            return Product.objects.all().prefetch_related('variants', 'seller', 'category')
        if hasattr(user, 'seller_profile'):
            return Product.objects.filter(seller=user.seller_profile).prefetch_related('variants', 'category')
        return Product.objects.none()

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return ProductCreateSerializer
        return ProductSerializer

    @extend_schema(summary="List seller/admin products")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Create a product (Seller/Admin)")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary="Retrieve product details")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary="Update a product")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(summary="Delete a product")
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(summary="Toggle product active/hidden status")
    @action(detail=True, methods=['post', 'patch'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        product = self.get_object()
        product.is_active = not product.is_active
        product.save()
        return Response(ProductSerializer(product).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='variants', serializer_class=VariantCreateSerializer)
    @extend_schema(summary="Add a variant to a product (Seller only)")
    def add_variant(self, request, pk=None):
        # Verify the product belongs to this seller
        seller = request.user.seller_profile
        product = get_object_or_404(Product, pk=pk, seller=seller)
        
        serializer = VariantCreateSerializer(
            data=request.data, 
            context={'request': request, 'product_id': product.id}
        )
        serializer.is_valid(raise_exception=True)
        variant = serializer.save()
        
        return Response(VariantSerializer(variant).data, status=status.HTTP_201_CREATED)


class AttributeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint to list and view attributes and their values.
    """
    queryset = Attribute.objects.prefetch_related('values').all()
    serializer_class = AttributeSerializer
    permission_classes = (permissions.AllowAny,)
