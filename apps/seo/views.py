from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.products.models import Product
from apps.categories.models import Category
from .schema import product_schema, category_schema, breadcrumb_list, organization_schema


@api_view(["GET"])
def product_schema_view(request, slug):
    try:
        product = Product.objects.select_related("category").prefetch_related(
            "images"
        ).get(slug=slug, is_active=True, soft_deleted=False)
    except Product.DoesNotExist:
        return Response({"error": "Product not found"}, status=404)
    return Response(product_schema(product, request))


@api_view(["GET"])
def category_schema_view(request, slug):
    try:
        category = Category.objects.get(slug=slug, is_active=True)
    except Category.DoesNotExist:
        return Response({"error": "Category not found"}, status=404)
    return Response(category_schema(category, request))


@api_view(["GET"])
def breadcrumb_view(request, slug):
    try:
        category = Category.objects.get(slug=slug, is_active=True)
    except Category.DoesNotExist:
        return Response({"error": "Category not found"}, status=404)
    crumbs = category.get_breadcrumb()
    return Response(breadcrumb_list(crumbs, request))


@api_view(["GET"])
def organization_schema_view(request):
    return Response(organization_schema(request))
