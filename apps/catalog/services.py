from django.db import transaction
from django.core.exceptions import ValidationError
from apps.catalog.models import (
    Category, Product, Attribute, AttributeValue, 
    Variant, VariantAttribute, ProductImage
)
from apps.sellers.models import SellerProfile

@transaction.atomic
def create_category(name, slug, parent=None, description=None):
    return Category.objects.create(
        name=name,
        slug=slug,
        parent=parent,
        description=description
    )


@transaction.atomic
def create_product(seller: SellerProfile, category: Category, name: str, slug: str, description: str):
    return Product.objects.create(
        seller=seller,
        category=category,
        name=name,
        slug=slug,
        description=description
    )


@transaction.atomic
def create_variant(product: Product, sku: str, price: float, discount_price=None, attribute_values=None):
    """
    Creates a product variant and links its attribute values.
    Validates that a variant cannot have multiple values for the same attribute (e.g. Size: Small and Size: Medium).
    """
    attribute_values = attribute_values or []
    
    # Validation: Ensure no duplicate attributes
    seen_attributes = set()
    for val in attribute_values:
        if val.attribute_id in seen_attributes:
            raise ValidationError(
                f"Variant cannot have multiple values for the same attribute: '{val.attribute.name}'."
            )
        seen_attributes.add(val.attribute_id)

    variant = Variant.objects.create(
        product=product,
        sku=sku,
        price=price,
        discount_price=discount_price
    )
    
    # Create links
    for val in attribute_values:
        VariantAttribute.objects.create(variant=variant, attribute_value=val)
        
    return variant


@transaction.atomic
def add_variant_image(variant: Variant, image_file, is_featured=False, alt_text=None):
    """
    Uploads and links an image to a variant. If is_featured is True, un-features other images for this variant.
    """
    if is_featured:
        ProductImage.objects.filter(variant=variant, is_featured=True).update(is_featured=False)
        
    return ProductImage.objects.create(
        variant=variant,
        image=image_file,
        is_featured=is_featured,
        alt_text=alt_text
    )
