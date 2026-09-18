from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from apps.accounts.permissions import IsAdmin, IsSeller
from apps.sellers.models import SellerProfile
from apps.sellers.serializers import (
    SellerPublicSerializer, 
    SellerDetailedSerializer, 
    SellerVerificationSerializer
)
from apps.sellers.selectors import get_active_sellers, get_seller_profile_by_user
from apps.sellers.services import update_seller_profile, verify_seller

class SellerPublicViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public API to browse verified active sellers.
    """
    serializer_class = SellerPublicSerializer
    permission_classes = (permissions.AllowAny,)
    queryset = get_active_sellers()

    @extend_schema(summary="List public verified sellers")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Retrieve public verified seller details")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class SellerMeView(generics.RetrieveUpdateAPIView):
    """
    API for sellers to manage their own business profiles.
    """
    serializer_class = SellerDetailedSerializer
    permission_classes = (IsSeller,)

    def get_object(self):
        return get_seller_profile_by_user(self.request.user)

    @extend_schema(summary="Get current seller profile")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Update current seller profile")
    def put(self, request, *args, **kwargs):
        profile = self.get_object()
        serializer = self.get_serializer(profile, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        update_seller_profile(profile, **serializer.validated_data)
        return Response(serializer.data)

    @extend_schema(summary="Partial update current seller profile")
    def patch(self, request, *args, **kwargs):
        profile = self.get_object()
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        update_seller_profile(profile, **serializer.validated_data)
        return Response(serializer.data)


class SellerVerifyView(APIView):
    """
    Admin endpoint to verify sellers and set commissions.
    """
    permission_classes = (IsAdmin,)

    @extend_schema(
        summary="Verify seller profile (Admin only)",
        request=SellerVerificationSerializer,
        responses={200: SellerDetailedSerializer}
    )
    def post(self, request, pk, *args, **kwargs):
        profile = get_object_or_404(SellerProfile, pk=pk)
        serializer = SellerVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        updated_profile = verify_seller(
            seller_profile=profile,
            status=serializer.validated_data['verification_status'],
            commission_percentage=serializer.validated_data.get('commission_percentage')
        )
        
        return Response(SellerDetailedSerializer(updated_profile).data, status=status.HTTP_200_OK)


class SellerAdminListView(generics.ListAPIView):
    """
    Admin-only endpoint to list all seller profiles (pending, approved, rejected).
    """
    queryset = SellerProfile.objects.select_related('user').all().order_by('-created_at')
    serializer_class = SellerDetailedSerializer
    permission_classes = (IsAdmin,)

    @extend_schema(summary="List all sellers for administration (Admin only)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

