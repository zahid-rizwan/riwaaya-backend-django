from rest_framework import serializers
from apps.cart.models import Cart, CartItem
from apps.catalog.serializers import VariantSerializer

class CartItemSerializer(serializers.ModelSerializer):
    variant = VariantSerializer(read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ('id', 'variant', 'quantity', 'subtotal')

    def get_subtotal(self, obj):
        price = obj.variant.discount_price if obj.variant.discount_price else obj.variant.price
        return price * obj.quantity


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ('id', 'items', 'total_items', 'total_price')

    def get_total_items(self, obj):
        return sum(item.quantity for item in obj.items.all())

    def get_total_price(self, obj):
        total = 0
        for item in obj.items.all():
            price = item.variant.discount_price if item.variant.discount_price else item.variant.price
            total += price * item.quantity
        return total


class CartAddUpdateSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, default=1)
