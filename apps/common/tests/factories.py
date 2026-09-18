import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

from apps.accounts.models import Address, UserRole
from apps.sellers.models import SellerProfile, VerificationStatus
from apps.catalog.models import Category, Product, Attribute, AttributeValue, Variant
from apps.inventory.models import Inventory
from apps.cart.models import Cart, CartItem
from apps.coupons.models import Coupon, DiscountType

User = get_user_model()

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.Sequence(lambda n: f"user_{n}@example.com")
    role = UserRole.CUSTOMER
    is_active = True


class SellerProfileFactory(DjangoModelFactory):
    class Meta:
        model = SellerProfile

    user = factory.SubFactory(UserFactory, role=UserRole.SELLER)
    business_name = factory.Sequence(lambda n: f"Seller Business {n}")
    gst_number = factory.Sequence(lambda n: f"07AAAAA{n:04d}A1Z1")
    pan = factory.Sequence(lambda n: f"ABCDE{n:04d}F")
    business_address = "123 Business Lane, Delhi"
    pickup_address = "123 Business Lane, Delhi"
    verification_status = VerificationStatus.APPROVED
    commission_percentage = Decimal("10.00")
    contact_phone = "9876543210"
    contact_email = factory.Sequence(lambda n: f"seller_{n}@example.com")


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")
    is_active = True


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    seller = factory.SubFactory(SellerProfileFactory)
    category = factory.SubFactory(CategoryFactory)
    name = factory.Sequence(lambda n: f"Product Name {n}")
    slug = factory.Sequence(lambda n: f"product-name-{n}")
    description = "Authentic couture design detailing premium craftsmanship."
    is_active = True


class AttributeFactory(DjangoModelFactory):
    class Meta:
        model = Attribute

    name = factory.Sequence(lambda n: f"Attribute {n}")
    slug = factory.Sequence(lambda n: f"attribute-{n}")


class AttributeValueFactory(DjangoModelFactory):
    class Meta:
        model = AttributeValue

    attribute = factory.SubFactory(AttributeFactory)
    value = factory.Sequence(lambda n: f"Value {n}")
    slug = factory.Sequence(lambda n: f"value-{n}")


class VariantFactory(DjangoModelFactory):
    class Meta:
        model = Variant

    product = factory.SubFactory(ProductFactory)
    sku = factory.Sequence(lambda n: f"SKU-CODE-{n}")
    price = Decimal("2500.00")
    is_active = True


class InventoryFactory(DjangoModelFactory):
    class Meta:
        model = Inventory

    variant = factory.SubFactory(VariantFactory)
    available_stock = 100
    reserved_stock = 0


class CartFactory(DjangoModelFactory):
    class Meta:
        model = Cart

    user = factory.SubFactory(UserFactory)


class CartItemFactory(DjangoModelFactory):
    class Meta:
        model = CartItem

    cart = factory.SubFactory(CartFactory)
    variant = factory.SubFactory(VariantFactory)
    quantity = 1


class CouponFactory(DjangoModelFactory):
    class Meta:
        model = Coupon

    code = factory.Sequence(lambda n: f"PROMO{n}")
    discount_type = DiscountType.FLAT
    discount_value = Decimal("500.00")
    min_order_value = Decimal("1000.00")
    start_date = factory.LazyFunction(timezone.now)
    end_date = factory.LazyFunction(lambda: timezone.now() + timezone.timedelta(days=30))
    is_active = True
