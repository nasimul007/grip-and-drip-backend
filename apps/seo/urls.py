from django.urls import path
from . import views

urlpatterns = [
    path("schema/<slug:slug>/", views.product_schema, name="product-schema"),
    path("organization/", views.organization_schema, name="organization-schema"),
]
