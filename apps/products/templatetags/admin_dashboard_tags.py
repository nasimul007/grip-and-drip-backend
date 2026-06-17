from django import template
from apps.products.models import Product, ProductVariant
from apps.categories.models import Category

register = template.Library()


@register.inclusion_tag("admin/dashboard_stats.html")
def admin_dashboard_stats():
    total_products = Product.objects.filter(soft_deleted=False).count()
    active_products = Product.objects.filter(
        is_active=True, soft_deleted=False
    ).count()
    total_categories = Category.objects.count()
    active_categories = Category.objects.filter(is_active=True).count()
    out_of_stock = Product.objects.filter(stock=0, soft_deleted=False).count()
    low_stock = (
        Product.objects.filter(stock__gt=0, stock__lte=5, soft_deleted=False)
        .count()
    )
    featured_products = Product.objects.filter(
        is_featured=True, soft_deleted=False
    ).count()
    total_variants = ProductVariant.objects.count()

    return {
        "total_products": total_products,
        "active_products": active_products,
        "total_categories": total_categories,
        "active_categories": active_categories,
        "out_of_stock": out_of_stock,
        "low_stock": low_stock,
        "featured_products": featured_products,
        "total_variants": total_variants,
    }
