import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from apps.accounts import services as account_services
from apps.accounts.models import Address, UserRole
from apps.sellers.models import SellerProfile
from apps.catalog import services as catalog_services
from apps.catalog.models import Variant
from apps.inventory import services as inventory_services
from apps.inventory.models import Inventory
from apps.cart import services as cart_services
from apps.orders import services as order_services
from apps.orders.models import OrderStatus, OrderItem
from apps.payments import services as payment_services
from apps.payments.models import PaymentStatus
from apps.payments.razorpay_provider import RazorpayGateway

from apps.common.tests.factories import (
    UserFactory, SellerProfileFactory, CategoryFactory, ProductFactory,
    AttributeFactory, AttributeValueFactory, VariantFactory, InventoryFactory,
    CartFactory, CartItemFactory, CouponFactory
)

User = get_user_model()

@pytest.mark.django_db
def test_customer_registration():
    """Verify customer registration creates correct role."""
    user = account_services.register_customer(
        username="john_doe",
        email="john@example.com",
        password="securepassword123",
        phone_number="1234567890"
    )
    assert user.role == UserRole.CUSTOMER
    assert user.check_password("securepassword123")


@pytest.mark.django_db
def test_seller_registration():
    """Verify seller registration creates user and profile atomically."""
    user, profile = account_services.register_seller(
        username="couture_seller",
        email="couture@example.com",
        password="sellerpassword123",
        business_name="Riwaaya Couture",
        gst_number="07AAAAA1111A1Z1",
        pan="ABCDE1234F",
        business_address="123 Street, Delhi",
        pickup_address="123 Street, Delhi",
        contact_phone="9876543210",
        contact_email="couture@example.com"
    )
    assert user.role == UserRole.SELLER
    assert profile.business_name == "Riwaaya Couture"
    assert profile.user == user


@pytest.mark.django_db
def test_default_address_constraint():
    """Verify that only one address of a type can be default for a user."""
    user = UserFactory()
    addr1 = account_services.create_address(
        user=user, address_type=Address.AddressType.SHIPPING,
        recipient_name="Home", phone_number="1", street_address="A",
        city="Delhi", state="DL", postal_code="110001", country="India",
        is_default=True
    )
    assert addr1.is_default
    
    addr2 = account_services.create_address(
        user=user, address_type=Address.AddressType.SHIPPING,
        recipient_name="Office", phone_number="2", street_address="B",
        city="Delhi", state="DL", postal_code="110001", country="India",
        is_default=True
    )
    
    # Reload addr1 from DB
    addr1.refresh_from_db()
    assert not addr1.is_default
    assert addr2.is_default


@pytest.mark.django_db
def test_variant_attribute_validation():
    """Verify that a variant cannot be created with duplicate attributes (e.g. two sizes)."""
    product = ProductFactory()
    size_attr = AttributeFactory(name="Size", slug="size")
    small_val = AttributeValueFactory(attribute=size_attr, value="Small", slug="small")
    medium_val = AttributeValueFactory(attribute=size_attr, value="Medium", slug="medium")

    with pytest.raises(ValidationError):
        catalog_services.create_variant(
            product=product,
            sku="SKU-ERR",
            price=1500.00,
            attribute_values=[small_val, medium_val]
        )


@pytest.mark.django_db
def test_stock_reservation():
    """Verify inventory is decremented from available and incremented in reserved during checkout."""
    variant = VariantFactory()
    inventory = InventoryFactory(variant=variant, available_stock=10, reserved_stock=2)

    inventory_services.reserve_stock(variant, 3)
    inventory.refresh_from_db()
    assert inventory.available_stock == 7
    assert inventory.reserved_stock == 5

    # Test insufficient stock raises ValidationError
    with pytest.raises(ValidationError):
        inventory_services.reserve_stock(variant, 10)


@pytest.mark.django_db
def test_stock_release_and_confirm():
    """Verify stock releases back to available or finalizes on payment success."""
    variant = VariantFactory()
    inventory = InventoryFactory(variant=variant, available_stock=5, reserved_stock=5)

    # Release stock (payment fails)
    inventory_services.release_stock(variant, 3)
    inventory.refresh_from_db()
    assert inventory.available_stock == 8
    assert inventory.reserved_stock == 2

    # Confirm sale (payment success)
    inventory_services.confirm_stock_sale(variant, 2)
    inventory.refresh_from_db()
    assert inventory.available_stock == 8
    assert inventory.reserved_stock == 0


@pytest.mark.django_db
def test_cart_management():
    """Verify add/update/remove items in the shopping cart."""
    user = UserFactory()
    variant = VariantFactory()
    InventoryFactory(variant=variant, available_stock=20)

    # Add to cart
    item = cart_services.add_item_to_cart(user, variant, 2)
    assert item.quantity == 2

    # Update quantity
    item = cart_services.update_cart_item_quantity(user, variant, 5)
    assert item.quantity == 5

    # Remove
    cart_services.remove_item_from_cart(user, variant)
    assert not user.cart.items.filter(variant=variant).exists()


@pytest.mark.django_db
def test_order_checkout_flow():
    """Verify full checkout flow with stock reservation, coupon discount, and price snapshotting."""
    customer = UserFactory()
    seller = SellerProfileFactory()
    category = CategoryFactory()
    product = ProductFactory(seller=seller, category=category)
    variant = VariantFactory(product=product, price=Decimal('2000.00'))
    InventoryFactory(variant=variant, available_stock=10)

    # Setup Cart
    cart_services.add_item_to_cart(customer, variant, 2)

    # Setup Addresses
    shipping_addr = Address.objects.create(
        user=customer, address_type=Address.AddressType.SHIPPING, recipient_name="John",
        phone_number="123", street_address="A", city="D", state="S", postal_code="Z", country="C"
    )
    billing_addr = Address.objects.create(
        user=customer, address_type=Address.AddressType.BILLING, recipient_name="John",
        phone_number="123", street_address="A", city="D", state="S", postal_code="Z", country="C"
    )

    # Setup Coupon (Flat 500 off, min purchase 1000)
    coupon = CouponFactory(code="OFF500", discount_type="FLAT", discount_value=Decimal('500.00'))

    # Checkout
    order, payment_session = order_services.create_order_from_cart(
        user=customer,
        shipping_address_id=shipping_addr.id,
        billing_address_id=billing_addr.id,
        coupon_code="OFF500"
    )

    # Assertions
    assert order.status == OrderStatus.PENDING
    assert order.subtotal == Decimal('4000.00')
    assert order.total_discount == Decimal('500.00')
    
    # 4000 subtotal + 150 shipping + 200 tax (5%) - 500 discount = 3850 total
    assert order.total_amount == Decimal('3850.00')

    # Verify stock reserved (10 - 2 = 8 available, 2 reserved)
    inventory = Inventory.objects.get(variant=variant)
    assert inventory.available_stock == 8
    assert inventory.reserved_stock == 2

    # Verify OrderItem snapshot details (price must be 2000)
    order_item = order.items.get(variant=variant)
    assert order_item.price == Decimal('2000.00')
    assert order_item.sku == variant.sku
    assert order_item.product_name == product.name

    # Fulfill payment (Webhook simulation)
    payment = payment_services.fulfill_payment(
        transaction_id=payment_session["id"],
        gateway_payload={"razorpay_order_id": payment_session["id"], "razorpay_payment_id": "pay_xyz"},
        signature="mock_sig"
    )
    
    order.refresh_from_db()
    assert order.status == OrderStatus.CONFIRMED
    assert payment.status == PaymentStatus.SUCCESS

    # Verify stock sale confirmed (reserved stock goes to 0, available remains 8)
    inventory.refresh_from_db()
    assert inventory.available_stock == 8
    assert inventory.reserved_stock == 0


@pytest.mark.django_db
def test_empty_cart_checkout():
    """Verify checking out with an empty cart raises ValidationError."""
    customer = UserFactory()
    shipping_addr = Address.objects.create(
        user=customer, address_type=Address.AddressType.SHIPPING, recipient_name="John",
        phone_number="123", street_address="A", city="D", state="S", postal_code="Z", country="C"
    )
    billing_addr = Address.objects.create(
        user=customer, address_type=Address.AddressType.BILLING, recipient_name="John",
        phone_number="123", street_address="A", city="D", state="S", postal_code="Z", country="C"
    )
    with pytest.raises(ValidationError):
        order_services.create_order_from_cart(
            user=customer,
            shipping_address_id=shipping_addr.id,
            billing_address_id=billing_addr.id
        )


@pytest.mark.django_db
def test_failed_payment_reverts_inventory_and_coupon():
    """Verify that a payment failure cancels the order, returns stock, and restores coupon use count."""
    customer = UserFactory()
    seller = SellerProfileFactory()
    category = CategoryFactory()
    product = ProductFactory(seller=seller, category=category)
    variant = VariantFactory(product=product, price=Decimal('1000.00'))
    InventoryFactory(variant=variant, available_stock=10, reserved_stock=0)

    cart_services.add_item_to_cart(customer, variant, 1)

    shipping_addr = Address.objects.create(
        user=customer, address_type=Address.AddressType.SHIPPING, recipient_name="John",
        phone_number="123", street_address="A", city="D", state="S", postal_code="Z", country="C"
    )
    billing_addr = Address.objects.create(
        user=customer, address_type=Address.AddressType.BILLING, recipient_name="John",
        phone_number="123", street_address="A", city="D", state="S", postal_code="Z", country="C"
    )
    coupon = CouponFactory(code="50OFF", discount_type="PERCENTAGE", discount_value=Decimal('50.00'))

    order, payment_session = order_services.create_order_from_cart(
        user=customer,
        shipping_address_id=shipping_addr.id,
        billing_address_id=billing_addr.id,
        coupon_code="50OFF"
    )

    coupon.refresh_from_db()
    assert coupon.used_count == 1
    inventory = Inventory.objects.get(variant=variant)
    assert inventory.available_stock == 9
    assert inventory.reserved_stock == 1

    # Simulate payment failure
    payment_services.fail_payment(transaction_id=payment_session["id"])
    
    order.refresh_from_db()
    coupon.refresh_from_db()
    inventory.refresh_from_db()

    assert order.status == OrderStatus.CANCELLED
    assert coupon.used_count == 0
    assert inventory.available_stock == 10
    assert inventory.reserved_stock == 0


@pytest.mark.django_db
def test_payment_already_processed():
    """Verify double-submitting a webhook fulfillment returns immediately for success status."""
    customer = UserFactory()
    seller = SellerProfileFactory()
    category = CategoryFactory()
    product = ProductFactory(seller=seller, category=category)
    variant = VariantFactory(product=product, price=Decimal('1000.00'))
    InventoryFactory(variant=variant, available_stock=5)

    cart_services.add_item_to_cart(customer, variant, 1)
    
    shipping_addr = Address.objects.create(
        user=customer, address_type=Address.AddressType.SHIPPING, recipient_name="John",
        phone_number="123", street_address="A", city="D", state="S", postal_code="Z", country="C"
    )
    billing_addr = Address.objects.create(
        user=customer, address_type=Address.AddressType.BILLING, recipient_name="John",
        phone_number="123", street_address="A", city="D", state="S", postal_code="Z", country="C"
    )
    
    order, payment_session = order_services.create_order_from_cart(
        user=customer,
        shipping_address_id=shipping_addr.id,
        billing_address_id=billing_addr.id
    )

    # First fulfillment
    payment = payment_services.fulfill_payment(
        transaction_id=payment_session["id"],
        gateway_payload={"razorpay_order_id": payment_session["id"]},
        signature="mock_sig"
    )
    assert payment.status == PaymentStatus.SUCCESS

    # Second fulfillment should return without raising error or re-decrementing
    payment = payment_services.fulfill_payment(
        transaction_id=payment_session["id"],
        gateway_payload={"razorpay_order_id": payment_session["id"]},
        signature="mock_sig"
    )
    assert payment.status == PaymentStatus.SUCCESS


@pytest.mark.django_db
def test_invalid_signature_validation(monkeypatch):
    """Verify that an invalid payment signature raises a ValidationError."""
    customer = UserFactory()
    seller = SellerProfileFactory()
    category = CategoryFactory()
    product = ProductFactory(seller=seller, category=category)
    variant = VariantFactory(product=product)
    InventoryFactory(variant=variant, available_stock=5)

    cart_services.add_item_to_cart(customer, variant, 1)
    
    shipping_addr = Address.objects.create(
        user=customer, address_type=Address.AddressType.SHIPPING, recipient_name="John",
        phone_number="123", street_address="A", city="D", state="S", postal_code="Z", country="C"
    )
    billing_addr = Address.objects.create(
        user=customer, address_type=Address.AddressType.BILLING, recipient_name="John",
        phone_number="123", street_address="A", city="D", state="S", postal_code="Z", country="C"
    )
    
    order, payment_session = order_services.create_order_from_cart(
        user=customer,
        shipping_address_id=shipping_addr.id,
        billing_address_id=billing_addr.id
    )

    # Mock payment verification to fail
    monkeypatch.setattr(RazorpayGateway, "verify_payment", lambda self, p, s: False)

    with pytest.raises(ValidationError):
        payment_services.fulfill_payment(
            transaction_id=payment_session["id"],
            gateway_payload={"razorpay_order_id": payment_session["id"]},
            signature="bad_sig"
        )

