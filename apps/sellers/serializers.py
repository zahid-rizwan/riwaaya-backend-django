from rest_framework import serializers
from apps.sellers.models import SellerProfile, VerificationStatus

class SellerPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerProfile
        fields = ('id', 'business_name', 'logo', 'contact_phone', 'contact_email')
        read_only_fields = fields


class SellerDetailedSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = SellerProfile
        fields = (
            'id', 'username', 'email', 'business_name', 'gst_number', 
            'pan', 'business_address', 'pickup_address', 'bank_details', 
            'verification_status', 'commission_percentage', 'logo', 
            'contact_phone', 'contact_email', 'created_at', 'updated_at'
        )
        read_only_fields = (
            'id', 'username', 'email', 'verification_status', 
            'commission_percentage', 'created_at', 'updated_at'
        )


class SellerVerificationSerializer(serializers.Serializer):
    verification_status = serializers.ChoiceField(choices=VerificationStatus.choices)
    commission_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
