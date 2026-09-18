from rest_framework import serializers
from apps.catalog.models import (
    Category, Product, Attribute, AttributeValue, 
    Variant, VariantAttribute, ProductImage
)
from apps.sellers.serializers import SellerPublicSerializer

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'description', 'parent')


class AttributeValueSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)

    class Meta:
        model = AttributeValue
        fields = ('id', 'attribute', 'attribute_name', 'value', 'slug')


class AttributeSerializer(serializers.ModelSerializer):
    values = AttributeValueSerializer(many=True, read_only=True)

    class Meta:
        model = Attribute
        fields = ('id', 'name', 'slug', 'values')


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ('id', 'image', 'is_featured', 'alt_text')


class VariantAttributeSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source='attribute_value.attribute.name', read_only=True)
    attribute_value_name = serializers.CharField(source='attribute_value.value', read_only=True)

    class Meta:
        model = VariantAttribute
        fields = ('id', 'attribute_value', 'attribute_name', 'attribute_value_name')


class VariantSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    attributes = VariantAttributeSerializer(source='variant_attributes', many=True, read_only=True)
    available_stock = serializers.IntegerField(source='inventory.available_stock', default=0, read_only=True)

    class Meta:
        model = Variant
        fields = ('id', 'sku', 'price', 'discount_price', 'is_active', 'images', 'attributes', 'available_stock')


class ProductSerializer(serializers.ModelSerializer):
    seller = SellerPublicSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    variants = VariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'seller', 'category', 'name', 'slug', 'description', 'is_active', 'variants', 'created_at')


class ProductCreateSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False, default=True)

    class Meta:
        model = Product
        fields = ('id', 'name', 'slug', 'description', 'category', 'is_active')

    def create(self, validated_data):
        from django.utils.text import slugify
        if not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data.get('name', ''))
        seller = self.context['request'].user.seller_profile
        return Product.objects.create(seller=seller, **validated_data)

    def update(self, instance, validated_data):
        from django.utils.text import slugify
        if 'name' in validated_data and not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data['name'])
        return super().update(instance, validated_data)


class VariantCreateSerializer(serializers.ModelSerializer):
    attribute_values = serializers.PrimaryKeyRelatedField(
        queryset=AttributeValue.objects.all(), 
        many=True, 
        required=False
    )
    available_stock = serializers.IntegerField(write_only=True, required=False, default=0)

    class Meta:
        model = Variant
        fields = ('sku', 'price', 'discount_price', 'attribute_values', 'available_stock')

    def create(self, validated_data):
        product_id = self.context['product_id']
        product = Product.objects.get(pk=product_id)
        attribute_values = validated_data.pop('attribute_values', [])
        available_stock = validated_data.pop('available_stock', 0)
        
        from apps.catalog.services import create_variant
        variant = create_variant(
            product=product,
            sku=validated_data['sku'],
            price=validated_data['price'],
            discount_price=validated_data.get('discount_price'),
            attribute_values=attribute_values
        )
        
        from apps.inventory.services import replenish_stock
        replenish_stock(variant, available_stock)
        
        return variant
