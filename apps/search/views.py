from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.pagination import LimitOffsetPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.catalog.serializers import ProductSerializer
from apps.search.selectors import search_catalog_products

class CatalogSearchView(APIView):
    """
    API view to query products using search terms.
    """
    permission_classes = (permissions.AllowAny,)

    @extend_schema(
        summary="Search products in catalog",
        parameters=[
            OpenApiParameter(name='q', type=str, description='Search query term', required=True)
        ],
        responses={200: ProductSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        query = request.query_params.get('q', '')
        if not query:
            return Response(
                {"error": "Query parameter 'q' is required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        products = search_catalog_products(query)
        
        paginator = LimitOffsetPagination()
        paginated_products = paginator.paginate_queryset(products, request, view=self)
        if paginated_products is not None:
            serializer = ProductSerializer(paginated_products, many=True)
            return paginator.get_paginated_response(serializer.data)
            
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)
