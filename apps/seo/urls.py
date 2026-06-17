from django.urls import path
from . import views

urlpatterns = [
    path("schema/product/<slug:slug>/", views.product_schema_view, name="product-schema"),
    path("schema/category/<slug:slug>/", views.category_schema_view, name="category-schema"),
    path("schema/<slug:slug>/", views.product_schema_view, name="product-schema-short"),
    path("breadcrumb/<slug:slug>/", views.breadcrumb_view, name="breadcrumb"),
    path("organization/", views.organization_schema_view, name="organization-schema"),
]
