import uuid
from django.db import models
from apps.sellers.models import SellerProfile

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    parent = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='children'
    )
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        full_path = [self.name]
        k = self.parent
        while k is not None:
            full_path.append(k.name)
            k = k.parent
        return ' -> '.join(full_path[::-1])


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        SellerProfile, 
        on_delete=models.CASCADE, 
        related_name='products'
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='products'
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField()
    group_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    color_name = models.CharField(max_length=80, blank=True, default='')
    color_hex = models.CharField(max_length=30, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Attribute(models.Model):
    """
    Represents the attribute name (e.g. Size, Color, Fabric).
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class AttributeValue(models.Model):
    """
    Represents values for an attribute (e.g. Small, Medium, Red, Blue, Cotton).
    """
    attribute = models.ForeignKey(
        Attribute, 
        on_delete=models.CASCADE, 
        related_name='values'
    )
    value = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        unique_together = ('attribute', 'value')

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class Variant(models.Model):
    """
    The purchasable SKU representing a specific combination of attributes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='variants'
    )
    sku = models.CharField(max_length=100, unique=True)
    size = models.CharField(max_length=30, blank=True, default='')
    color = models.CharField(max_length=80, blank=True, default='')
    color_hex = models.CharField(max_length=30, blank=True, default='#B8963E')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.sku} ({self.price})"


class VariantAttribute(models.Model):
    """
    M2M Through table linking Variant to AttributeValue.
    """
    variant = models.ForeignKey(
        Variant, 
        on_delete=models.CASCADE, 
        related_name='variant_attributes'
    )
    attribute_value = models.ForeignKey(
        AttributeValue, 
        on_delete=models.CASCADE,
        related_name='variant_links'
    )

    class Meta:
        unique_together = ('variant', 'attribute_value')

    def __str__(self):
        return f"{self.variant.sku} -> {self.attribute_value}"


class ProductImage(models.Model):
    variant = models.ForeignKey(
        Variant, 
        on_delete=models.CASCADE, 
        related_name='images'
    )
    image = models.ImageField(upload_to='product_images/', max_length=500)
    is_featured = models.BooleanField(default=False)
    alt_text = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.variant.sku}"
