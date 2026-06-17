from django.urls import path
from . import views

urlpatterns = [
    path("", views.ProductSearchView.as_view(), name="product-search"),
]
