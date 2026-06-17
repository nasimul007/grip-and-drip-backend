from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from apps.categories.models import Category
from apps.products.models import Product


class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Category.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at


class ProductSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        return Product.objects.filter(is_active=True, soft_deleted=False)

    def lastmod(self, obj):
        return obj.updated_at


class StaticViewSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return ["category-tree", "product-list"]

    def location(self, item):
        return reverse(item)


sitemaps = {
    "categories": CategorySitemap,
    "products": ProductSitemap,
    "static": StaticViewSitemap,
}
