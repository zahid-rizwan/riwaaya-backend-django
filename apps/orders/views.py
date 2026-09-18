from rest_framework import viewsets, permissions, status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from apps.accounts.permissions import IsSeller
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer, OrderCreateSerializer
from apps.orders.selectors import get_user_orders, get_order_by_id, get_seller_orders
from apps.orders.services import create_order_from_cart

class OrderViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for managing orders. Customers can view/place orders.
    """
    serializer_class = OrderSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return get_user_orders(self.request.user)

    @extend_schema(summary="List customer's orders")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Retrieve specific order details")
    def retrieve(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        order = get_order_by_id(request.user, pk)
        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @extend_schema(
        summary="Create an order from the active cart (Checkout)",
        request=OrderCreateSerializer,
        responses={201: OrderSerializer}
    )
    def create(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order, payment_session = create_order_from_cart(
            user=request.user,
            shipping_address_id=serializer.validated_data['shipping_address_id'],
            billing_address_id=serializer.validated_data['billing_address_id'],
            coupon_code=serializer.validated_data.get('coupon_code')
        )
        
        return Response({
            "order": OrderSerializer(order).data,
            "payment_session": payment_session
        }, status=status.HTTP_201_CREATED)


class SellerOrderListView(generics.ListAPIView):
    """
    API endpoint for sellers to list orders containing their products.
    """
    serializer_class = OrderSerializer
    permission_classes = (IsSeller,)

    def get_queryset(self):
        seller = self.request.user.seller_profile
        return get_seller_orders(seller)

    @extend_schema(summary="List seller's incoming orders (Seller only)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
