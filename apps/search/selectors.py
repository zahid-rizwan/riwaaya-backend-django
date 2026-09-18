from django.db import connection, models
from django.db.models import Q
from apps.catalog.models import Product

def search_catalog_products(query_text: str) -> models.QuerySet:
    """
    Search selector querying products by title and description.
    Uses PostgreSQL Full-Text Search when running on Postgres, 
    and falls back to standard Q-lookups for SQLite (e.g. unit testing).
    """
    if not query_text:
        return Product.objects.filter(is_active=True)

    if connection.vendor == 'postgresql':
        from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
        
        # Weighted vector: Product name has priority A, description priority B
        vector = SearchVector('name', weight='A') + SearchVector('description', weight='B')
        query = SearchQuery(query_text)
        
        return Product.objects.filter(is_active=True).annotate(
            rank=SearchRank(vector, query)
        ).filter(rank__gte=0.05).order_by('-rank')
    else:
        # Fallback for local sqlite / testing
        return Product.objects.filter(
            Q(name__icontains=query_text) | Q(description__icontains=query_text),
            is_active=True
        )
