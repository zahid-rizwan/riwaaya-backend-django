from django.db.models import QuerySet
from apps.catalog.models import Category, Product, Variant

def get_active_products() -> QuerySet:
    """
    Selector to retrieve active products with optimized pre-fetches.
    """
    return Product.objects.filter(is_active=True).select_related(
        'seller', 'category'
    ).prefetch_related(
        'variants__images', 
        'variants__variant_attributes__attribute_value__attribute'
    )


def get_product_by_slug(slug: str) -> Product:
    """
    Selector to retrieve a single product by slug.
    """
    return Product.objects.filter(is_active=True).select_related(
        'seller', 'category'
    ).prefetch_related(
        'variants__images', 
        'variants__variant_attributes__attribute_value__attribute'
    ).get(slug=slug)


def get_categories() -> QuerySet:
    """
    Retrieves active categories.
    """
    return Category.objects.filter(is_active=True)


def get_descendant_categories(category: Category) -> list:
    """
    Helper to recursively get all sub-category instances.
    """
    descendants = [category]
    for child in category.children.filter(is_active=True):
        descendants.extend(get_descendant_categories(child))
    return descendants


def get_products_in_category(category_slug: str) -> QuerySet:
    """
    Retrieves all products in a given category or any of its sub-categories.
    """
    category = Category.objects.get(slug=category_slug, is_active=True)
    categories = get_descendant_categories(category)
    return get_active_products().filter(category__in=categories)
