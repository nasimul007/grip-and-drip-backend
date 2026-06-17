from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.products.models import Product
from apps.products.serializers import generate_product_schema


@api_view(["GET"])
def product_schema(request, slug):
    try:
        product = Product.objects.get(slug=slug, is_active=True, soft_deleted=False)
    except Product.DoesNotExist:
        return Response({"error": "Product not found"}, status=404)
    schema = generate_product_schema(product, request)
    return Response(schema)


@api_view(["GET"])
def organization_schema(request):
    site_url = f"{request.scheme}://{request.get_host()}"
    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Grip & Drip",
        "url": site_url,
        "description": "Premium mobile covers, wallets, and card holders.",
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{site_url}/api/search/?q={{search_term_string}}",
            },
            "query-input": "required name=search_term_string",
        },
    }
    return Response(schema)
