import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from apps.catalog.models import Category, Attribute, AttributeValue

def seed():
    print("Seeding catalog database...")
    
    # 1. Seed Categories
    categories_data = [
        {"name": "Womens Wear", "slug": "womens-wear", "description": "Designer lehengas, salwar kameez, lawn suits, and sarees."},
        {"name": "Mens Wear", "slug": "mens-wear", "description": "Premium sherwanis, kurtas, and waistcoats."},
        {"name": "Accessories", "slug": "accessories", "description": "Traditional jewelry, shawls, and footwear."},
    ]
    
    categories = {}
    for cat in categories_data:
        obj, created = Category.objects.get_or_create(
            slug=cat["slug"],
            defaults={"name": cat["name"], "description": cat["description"]}
        )
        categories[cat["slug"]] = obj
        if created:
            print(f"Created Category: {obj.name}")
        else:
            print(f"Category already exists: {obj.name}")

    # 2. Seed Attributes
    attributes_data = [
        {"name": "Size", "slug": "size"},
        {"name": "Color", "slug": "color"},
        {"name": "Fabric", "slug": "fabric"},
    ]
    
    attributes = {}
    for attr in attributes_data:
        obj, created = Attribute.objects.get_or_create(
            slug=attr["slug"],
            defaults={"name": attr["name"]}
        )
        attributes[attr["slug"]] = obj
        if created:
            print(f"Created Attribute: {obj.name}")
        else:
            print(f"Attribute already exists: {obj.name}")

    # 3. Seed Attribute Values
    values_data = [
        # Size Values
        {"attribute": "size", "value": "S", "slug": "size-s"},
        {"attribute": "size", "value": "M", "slug": "size-m"},
        {"attribute": "size", "value": "L", "slug": "size-l"},
        {"attribute": "size", "value": "XL", "slug": "size-xl"},
        # Color Values
        {"attribute": "color", "value": "Emerald Green", "slug": "color-emerald-green"},
        {"attribute": "color", "value": "Crimson Red", "slug": "color-crimson-red"},
        {"attribute": "color", "value": "Royal Blue", "slug": "color-royal-blue"},
        {"attribute": "color", "value": "Gold", "slug": "color-gold"},
        # Fabric Values
        {"attribute": "fabric", "value": "Lawn", "slug": "fabric-lawn"},
        {"attribute": "fabric", "value": "Silk", "slug": "fabric-silk"},
        {"attribute": "fabric", "value": "Chiffon", "slug": "fabric-chiffon"},
        {"attribute": "fabric", "value": "Cotton", "slug": "fabric-cotton"},
    ]

    for val in values_data:
        parent_attr = attributes[val["attribute"]]
        obj, created = AttributeValue.objects.get_or_create(
            slug=val["slug"],
            defaults={"attribute": parent_attr, "value": val["value"]}
        )
        if created:
            print(f"  Created AttributeValue: {obj}")
        else:
            print(f"  AttributeValue already exists: {obj}")

    print("Database seeding completed successfully!")

if __name__ == "__main__":
    seed()
