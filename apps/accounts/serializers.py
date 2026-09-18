from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.accounts.models import Address, UserRole
from apps.accounts import services
from apps.sellers.models import SellerProfile

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role', 'phone_number')
        read_only_fields = ('id', 'role')


class CustomerRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def create(self, validated_data):
        return services.register_customer(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            phone_number=validated_data.get('phone_number')
        )


class SellerRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    
    # SellerProfile fields
    business_name = serializers.CharField(max_length=255)
    gst_number = serializers.CharField(max_length=15)
    pan = serializers.CharField(max_length=10)
    business_address = serializers.CharField()
    pickup_address = serializers.CharField()
    bank_details = serializers.JSONField(required=False)
    contact_phone = serializers.CharField(max_length=20)
    contact_email = serializers.EmailField()

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate_gst_number(self, value):
        if SellerProfile.objects.filter(gst_number=value).exists():
            raise serializers.ValidationError("A seller with this GST number is already registered.")
        return value

    def validate_pan(self, value):
        if SellerProfile.objects.filter(pan=value).exists():
            raise serializers.ValidationError("A seller with this PAN is already registered.")
        return value

    def create(self, validated_data):
        user, profile = services.register_seller(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            business_name=validated_data['business_name'],
            gst_number=validated_data['gst_number'],
            pan=validated_data['pan'],
            business_address=validated_data['business_address'],
            pickup_address=validated_data['pickup_address'],
            contact_phone=validated_data['contact_phone'],
            contact_email=validated_data['contact_email'],
            bank_details=validated_data.get('bank_details', {})
        )
        return user


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            'id', 'address_type', 'is_default', 'recipient_name', 
            'phone_number', 'street_address', 'city', 'state', 
            'postal_code', 'country', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def create(self, validated_data):
        user = self.context['request'].user
        return services.create_address(user=user, **validated_data)

    def update(self, instance, validated_data):
        return services.update_address(address=instance, **validated_data)
