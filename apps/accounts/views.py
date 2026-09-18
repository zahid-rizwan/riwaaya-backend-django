from rest_framework import generics, viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema

from apps.accounts.models import Address
from apps.accounts.serializers import (
    UserSerializer, 
    CustomerRegisterSerializer, 
    SellerRegisterSerializer,
    AddressSerializer
)
from apps.accounts.selectors import get_user_addresses

User = get_user_model()

class CustomerRegisterView(generics.CreateAPIView):
    serializer_class = CustomerRegisterSerializer
    permission_classes = (permissions.AllowAny,)

    @extend_schema(summary="Register a new customer")
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class SellerRegisterView(generics.CreateAPIView):
    serializer_class = SellerRegisterSerializer
    permission_classes = (permissions.AllowAny,)

    @extend_schema(summary="Register a new seller")
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class UserMeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(summary="Get current user details")
    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @extend_schema(summary="Update current user details")
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(summary="Partial update current user details")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return get_user_addresses(self.request.user)

    @extend_schema(summary="List user addresses")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Create a user address")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary="Retrieve a user address details")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary="Update a user address")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(summary="Delete a user address")
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
