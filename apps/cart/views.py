from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from apps.catalog.models import Variant
from apps.cart.selectors import get_user_cart
from apps.cart.serializers import CartSerializer, CartAddUpdateSerializer
from apps.cart import services

class CartView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        summary="Get current user's shopping cart",
        responses={200: CartSerializer}
    )
    def get(self, request, *args, **kwargs):
        cart = get_user_cart(request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    @extend_schema(
        summary="Add an item to the shopping cart",
        request=CartAddUpdateSerializer,
        responses={200: CartSerializer}
    )
    def post(self, request, *args, **kwargs):
        serializer = CartAddUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        variant = get_object_or_404(Variant, pk=serializer.validated_data['variant_id'])
        services.add_item_to_cart(
            user=request.user, 
            variant=variant, 
            quantity=serializer.validated_data['quantity']
        )
        
        # Return updated cart
        cart = get_user_cart(request.user)
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class CartItemUpdateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        summary="Update item quantity in the cart",
        request=CartAddUpdateSerializer,
        responses={200: CartSerializer}
    )
    def post(self, request, *args, **kwargs):
        serializer = CartAddUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        variant = get_object_or_404(Variant, pk=serializer.validated_data['variant_id'])
        services.update_cart_item_quantity(
            user=request.user, 
            variant=variant, 
            quantity=serializer.validated_data['quantity']
        )
        
        cart = get_user_cart(request.user)
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class CartItemRemoveView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        summary="Remove an item from the shopping cart",
        responses={200: CartSerializer}
    )
    def post(self, request, variant_id, *args, **kwargs):
        variant = get_object_or_404(Variant, pk=variant_id)
        services.remove_item_from_cart(user=request.user, variant=variant)
        
        cart = get_user_cart(request.user)
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class CartClearView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        summary="Clear the shopping cart",
        responses={200: CartSerializer}
    )
    def post(self, request, *args, **kwargs):
        cart = get_user_cart(request.user)
        services.clear_cart(cart)
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)
