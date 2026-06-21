from django.urls import path
from . import views

urlpatterns = [
    path("cart/", views.CartView.as_view(), name="cart-detail"),
    path("cart/add/", views.CartAddItemView.as_view(), name="cart-add"),
    path("cart/items/<int:item_id>/", views.CartItemUpdateView.as_view(), name="cart-item-update"),
    path("cart/items/<int:item_id>/remove/", views.CartItemRemoveView.as_view(), name="cart-item-remove"),
    path("cart/clear/", views.CartClearView.as_view(), name="cart-clear"),
    path("shipping-rates/", views.ShippingRateListView.as_view(), name="shipping-rates"),
    path("orders/", views.OrderCreateView.as_view(), name="order-create"),
    path("orders/list/", views.OrderListView.as_view(), name="order-list"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order-detail"),
]
