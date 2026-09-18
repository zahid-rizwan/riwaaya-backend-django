from django.urls import path
from apps.cart.views import CartView, CartItemUpdateView, CartItemRemoveView, CartClearView

urlpatterns = [
    path('', CartView.as_view(), name='cart'),
    path('update/', CartItemUpdateView.as_view(), name='cart_update'),
    path('remove/<uuid:variant_id>/', CartItemRemoveView.as_view(), name='cart_remove'),
    path('clear/', CartClearView.as_view(), name='cart_clear'),
]
