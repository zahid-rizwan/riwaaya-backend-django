from rest_framework import serializers
from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment

class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            'id', 'variant', 'product_name', 'sku', 
            'variant_details', 'price', 'discount', 
            'tax', 'quantity', 'subtotal'
        )

    def get_subtotal(self, obj):
        return (obj.price - obj.discount + obj.tax) * obj.quantity


class OrderPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ('id', 'transaction_id', 'provider', 'amount', 'status', 'created_at')


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payments = OrderPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'status', 'shipping_address', 'billing_address', 
            'shipping_cost', 'tax', 'coupon', 'total_discount', 
            'subtotal', 'total_amount', 'created_at', 'updated_at', 
            'items', 'payments'
        )


class OrderCreateSerializer(serializers.Serializer):
    shipping_address_id = serializers.UUIDField()
    billing_address_id = serializers.UUIDField()
    coupon_code = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
