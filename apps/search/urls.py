from django.urls import path
from apps.search.views import CatalogSearchView

urlpatterns = [
    path('', CatalogSearchView.as_view(), name='catalog_search'),
]
