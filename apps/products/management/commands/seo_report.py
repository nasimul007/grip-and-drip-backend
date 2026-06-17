from django.core.management.base import BaseCommand
from django.test import RequestFactory
from apps.categories.models import Category
from apps.products.models import Product
from apps.seo.schema import product_schema, category_schema


class Command(BaseCommand):
    help = "Generates an SEO report showing missing meta tags, schema issues, and optimization opportunities"

    def handle(self, *args, **options):
        factory = RequestFactory()
        request = factory.get("/")

        self.stdout.write("=" * 70)
        self.stdout.write("SEO REPORT - Grip & Drip E-Commerce")
        self.stdout.write("=" * 70)

        self._report_product_meta()
        self._report_category_meta()
        self._report_schema_issues(request)
        self._report_general_stats()

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("SEO report generated."))

    def _report_product_meta(self):
        self.stdout.write("\n--- Product Meta Tags ---")
        total = Product.objects.filter(soft_deleted=False).count()
        active = Product.objects.filter(is_active=True, soft_deleted=False).count()
        no_meta_title = Product.objects.filter(meta_title="", soft_deleted=False).count()
        no_meta_desc = Product.objects.filter(meta_description="", soft_deleted=False).count()
        no_brand = Product.objects.filter(brand="", soft_deleted=False).count()
        no_sku = Product.objects.filter(sku="", soft_deleted=False).count()
        no_og_image = Product.objects.filter(og_image="", soft_deleted=False).count()
        soft_deleted = Product.objects.filter(soft_deleted=True).count()

        self.stdout.write(f"  Total products: {total} ({active} active, {soft_deleted} soft-deleted)")
        self._seo_line("Missing meta title", no_meta_title, total)
        self._seo_line("Missing meta description", no_meta_desc, total)
        self._seo_line("Missing brand", no_brand, total)
        self._seo_line("Missing SKU", no_sku, total)
        self._seo_line("Missing OG image", no_og_image, total)

    def _report_category_meta(self):
        self.stdout.write("\n--- Category Meta Tags ---")
        total = Category.objects.count()
        active = Category.objects.filter(is_active=True).count()
        no_meta_title = Category.objects.filter(meta_title="").count()
        no_meta_desc = Category.objects.filter(meta_description="").count()
        no_og_image = Category.objects.filter(og_image="").count()
        no_description = Category.objects.filter(description="").count()

        self.stdout.write(f"  Total categories: {total} ({active} active)")
        self._seo_line("Missing meta title", no_meta_title, total)
        self._seo_line("Missing meta description", no_meta_desc, total)
        self._seo_line("Missing OG image", no_og_image, total)
        self._seo_line("Missing description", no_description, total)

    def _report_schema_issues(self, request):
        self.stdout.write("\n--- Schema Markup Issues ---")
        schema_errors = 0
        products = Product.objects.filter(is_active=True, soft_deleted=False).select_related("category").prefetch_related("images")
        for product in products:
            try:
                schema = product_schema(product, request)
                if not schema.get("offers"):
                    self.stdout.write(self.style.WARNING(f"  Product '{product.name}': Missing offers in schema"))
                    schema_errors += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Product '{product.name}': Schema generation failed - {e}"))
                schema_errors += 1

        categories = Category.objects.filter(is_active=True)
        for category in categories:
            try:
                schema = category_schema(category, request)
                if not schema.get("mainEntity"):
                    self.stdout.write(self.style.WARNING(f"  Category '{category.name}': Missing mainEntity in schema"))
                    schema_errors += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Category '{category.name}': Schema generation failed - {e}"))
                schema_errors += 1

        if schema_errors == 0:
            self.stdout.write(self.style.SUCCESS("  No schema issues found."))

    def _report_general_stats(self):
        self.stdout.write("\n--- General Stats ---")
        out_of_stock = Product.objects.filter(stock=0, is_active=True, soft_deleted=False).count()
        low_stock = Product.objects.filter(stock__gt=0, stock__lte=5, is_active=True, soft_deleted=False).count()
        featured = Product.objects.filter(is_featured=True, is_active=True, soft_deleted=False).count()
        categories_with_products = Category.objects.filter(products__is_active=True, products__soft_deleted=False).distinct().count()

        self.stdout.write(f"  Out-of-stock products: {out_of_stock}")
        self.stdout.write(f"  Low-stock products (1-5): {low_stock}")
        self.stdout.write(f"  Featured products: {featured}")
        self.stdout.write(f"  Categories with active products: {categories_with_products}")

    def _seo_line(self, label, count, total):
        if count == 0:
            self.stdout.write(self.style.SUCCESS(f"  {label}: {count}/{total}"))
        elif count <= total * 0.1:
            self.stdout.write(self.style.WARNING(f"  {label}: {count}/{total}"))
        else:
            self.stdout.write(self.style.ERROR(f"  {label}: {count}/{total}"))
