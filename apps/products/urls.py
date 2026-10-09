from django.urls import path
from . import views

urlpatterns = [
    path("", views.ProductListView.as_view(), name="product-list"),
    # Must stay above the slug route, which would otherwise match "filters".
    path("filters/", views.ProductFilterOptionsView.as_view(), name="product-filters"),
    path("<slug:slug>/", views.ProductDetailView.as_view(), name="product-detail"),
    path(
        "<slug:slug>/related/",
        views.RelatedProductsView.as_view(),
        name="product-related",
    ),
]
