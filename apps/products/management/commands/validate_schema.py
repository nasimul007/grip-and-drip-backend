from django.core.management.base import BaseCommand
from django.test import RequestFactory
from apps.categories.models import Category
from apps.products.models import Product
from apps.seo.schema import product_schema, category_schema, breadcrumb_list

REQUIRED_PRODUCT_FIELDS = ["@context", "@type", "name", "description", "sku", "offers", "url"]
REQUIRED_OFFER_FIELDS = ["@type", "price", "priceCurrency", "availability", "url"]
REQUIRED_CATEGORY_FIELDS = ["@context", "@type", "name", "description", "url", "mainEntity"]
REQUIRED_BREADCRUMB_FIELDS = ["@context", "@type", "itemListElement"]


class Command(BaseCommand):
    help = "Validates JSON-LD schema markup for all active products and categories"

    def handle(self, *args, **options):
        factory = RequestFactory()
        request = factory.get("/")
        errors = []
        warnings = []
        total_products = 0
        total_categories = 0

        self.stdout.write("Validating product schema markup...")
        products = Product.objects.filter(is_active=True, soft_deleted=False).select_related("category").prefetch_related("images")
        for product in products:
            total_products += 1
            try:
                schema = product_schema(product, request)
                errors += self._validate_product_schema(schema, product)
            except Exception as e:
                errors.append(f"  Product '{product.name}' (slug: {product.slug}): ERROR - {e}")

        self.stdout.write("Validating category schema markup...")
        categories = Category.objects.filter(is_active=True)
        for category in categories:
            total_categories += 1
            try:
                schema = category_schema(category, request)
                errors += self._validate_category_schema(schema, category)
            except Exception as e:
                errors.append(f"  Category '{category.name}' (slug: {category.slug}): ERROR - {e}")

            try:
                breadcrumbs = category.get_breadcrumb()
                breadcrumb_schema = breadcrumb_list(breadcrumbs, request)
                errors += self._validate_breadcrumb_schema(breadcrumb_schema, category)
            except Exception as e:
                errors.append(f"  Breadcrumb for '{category.name}': ERROR - {e}")

        self.stdout.write("\n" + "=" * 60)
        self._report("Product Schemas", total_products, errors, warnings)
        self._report("Category Schemas", total_categories, errors, warnings)
        self._report("Breadcrumbs", total_categories, errors, warnings)

        if errors:
            self.stdout.write(self.style.ERROR(f"\nFound {len(errors)} schema error(s):"))
            for error in errors:
                self.stdout.write(self.style.ERROR(error))
        else:
            self.stdout.write(self.style.SUCCESS("\nAll schema markup validated successfully!"))

    def _validate_product_schema(self, schema, product):
        issues = []
        for field in REQUIRED_PRODUCT_FIELDS:
            if field not in schema:
                issues.append(f"  Product '{product.name}': Missing required field '{field}'")
        if "offers" in schema:
            for field in REQUIRED_OFFER_FIELDS:
                if field not in schema["offers"]:
                    issues.append(f"  Product '{product.name}': Missing required offer field '{field}'")
        if "image" not in schema and product.images.exists():
            issues.append(f"  Product '{product.name}': Has images but schema missing 'image' field")
        if schema.get("@type") != "Product":
            issues.append(f"  Product '{product.name}': @type should be 'Product', got '{schema.get('@type')}'")
        return issues

    def _validate_category_schema(self, schema, category):
        issues = []
        for field in REQUIRED_CATEGORY_FIELDS:
            if field not in schema:
                issues.append(f"  Category '{category.name}': Missing required field '{field}'")
        if schema.get("@type") != "CollectionPage":
            issues.append(f"  Category '{category.name}': @type should be 'CollectionPage', got '{schema.get('@type')}'")
        main_entity = schema.get("mainEntity", {})
        if main_entity.get("@type") != "ItemList":
            issues.append(f"  Category '{category.name}': mainEntity.@type should be 'ItemList'")
        item_list = main_entity.get("itemListElement", [])
        for item in item_list:
            if item.get("@type") != "ListItem":
                issues.append(f"  Category '{category.name}': ItemList element @type should be 'ListItem'")
                break
        return issues

    def _validate_breadcrumb_schema(self, schema, category):
        issues = []
        for field in REQUIRED_BREADCRUMB_FIELDS:
            if field not in schema:
                issues.append(f"  Breadcrumb '{category.name}': Missing required field '{field}'")
        if schema.get("@type") != "BreadcrumbList":
            issues.append(f"  Breadcrumb '{category.name}': @type should be 'BreadcrumbList'")
        return issues

    def _report(self, label, count, errors, warnings):
        related_errors = [e for e in errors if label[:-1].lower() in e.lower()]
        status = self.style.SUCCESS("PASS") if not related_errors else self.style.ERROR("FAIL")
        self.stdout.write(f"  [{status}] {label}: {count} checked, {len(related_errors)} issues")
