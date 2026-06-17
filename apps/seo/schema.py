from apps.products.models import Product
from apps.categories.models import Category


def product_schema(product: Product, request=None) -> dict:
    site_url = _site_url(request)
    product_url = f"{site_url}/api/products/{product.slug}/" if site_url else ""
    image_urls = _product_images(product, site_url)

    offer = {
        "@type": "Offer",
        "url": product_url,
        "priceCurrency": "BDT",
        "price": str(product.effective_price),
        "availability": (
            "https://schema.org/InStock"
            if product.in_stock
            else "https://schema.org/OutOfStock"
        ),
        "itemCondition": "https://schema.org/NewCondition",
        "hasMerchantReturnPolicy": _return_policy(),
        "shippingDetails": _shipping_details(),
    }

    if product.has_discount:
        offer["priceSpecification"] = {
            "@type": "UnitPriceSpecification",
            "price": str(product.price),
            "priceCurrency": "BDT",
        }

    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "@id": product_url,
        "name": product.get_meta_title(),
        "description": product.get_meta_description(),
        "sku": product.sku,
        "brand": {
            "@type": "Brand",
            "name": product.brand or "Grip & Drip",
        },
        "offers": offer,
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "0",
            "reviewCount": "0",
            "bestRating": "5",
        },
    }

    if image_urls:
        schema["image"] = image_urls

    if product_url:
        schema["url"] = product_url

    return schema


def category_schema(category: Category, request=None) -> dict:
    site_url = _site_url(request)
    category_url = f"{site_url}/api/categories/{category.slug}/" if site_url else ""
    products = Product.objects.filter(
        category=category, is_active=True, soft_deleted=False
    )[:20]

    item_list = []
    for idx, product in enumerate(products, start=1):
        product_url = f"{site_url}/api/products/{product.slug}/" if site_url else ""
        item_list.append({
            "@type": "ListItem",
            "position": idx,
            "item": {
                "@type": "Product",
                "name": product.name,
                "sku": product.sku,
                "url": product_url,
                "offers": {
                    "@type": "Offer",
                    "price": str(product.effective_price),
                    "priceCurrency": "BDT",
                },
            },
        })

    return {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": category.get_meta_title(),
        "description": category.get_meta_description(),
        "url": category_url,
        "mainEntity": {
            "@type": "ItemList",
            "itemListElement": item_list,
        },
    }


def breadcrumb_list(breadcrumbs: list, request=None) -> dict:
    site_url = _site_url(request)
    item_list = []
    for idx, crumb in enumerate(breadcrumbs, start=1):
        crumb_url = f"{site_url}/api/categories/{crumb['slug']}/" if site_url else ""
        item_list.append({
            "@type": "ListItem",
            "position": idx,
            "name": crumb["name"],
            "item": crumb_url,
        })

    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": item_list,
    }


def organization_schema(request=None) -> dict:
    site_url = _site_url(request)
    return {
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


def _site_url(request) -> str:
    if request:
        try:
            host = request.get_host()
        except Exception:
            host = "localhost:8000"
        return f"{request.scheme}://{host}"
    return ""


def _product_images(product: Product, site_url: str) -> list:
    images = product.images.filter(is_primary=True)
    if not images.exists():
        images = product.images.all()[:1]
    urls = []
    for img in images:
        if img.image and site_url:
            urls.append(f"{site_url}{img.image.url}")
    return urls


def _return_policy() -> dict:
    return {
        "@type": "MerchantReturnPolicy",
        "applicableCountry": "BD",
        "returnPolicyCategory": (
            "https://schema.org/MerchantReturnFiniteReturnWindow"
        ),
        "merchantReturnDays": 7,
        "returnMethod": "https://schema.org/ReturnByMail",
        "returnFees": "https://schema.org/FreeReturn",
    }


def _shipping_details() -> dict:
    return {
        "@type": "OfferShippingDetails",
        "shippingDestination": {
            "@type": "DefinedRegion",
            "addressCountry": "BD",
        },
        "shippingRate": {
            "@type": "MonetaryAmount",
            "value": 60,
            "currency": "BDT",
        },
        "deliveryTime": {
            "@type": "ShippingDeliveryTime",
            "handlingTime": {
                "@type": "QuantitativeValue",
                "minValue": 1,
                "maxValue": 2,
                "unitCode": "DAY",
            },
            "transitTime": {
                "@type": "QuantitativeValue",
                "minValue": 2,
                "maxValue": 5,
                "unitCode": "DAY",
            },
        },
    }
