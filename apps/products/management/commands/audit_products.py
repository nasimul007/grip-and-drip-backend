import csv

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.products.models import Product


class Command(BaseCommand):
    help = "Report products missing images, description or specs; optionally export them to CSV."

    def add_arguments(self, parser):
        parser.add_argument("--export", metavar="FILE",
                            help="Write incomplete products to FILE (id, sku, name, brand, category, missing, url)")

    def handle(self, *args, **opts):
        products = (
            Product.objects.filter(soft_deleted=False)
            .select_related("category")
            .annotate(image_count=Count("images"))
            .order_by("id")
        )
        total = no_images = no_desc = no_specs = 0
        rows = []
        for p in products:
            total += 1
            missing = []
            if p.image_count == 0:
                no_images += 1
                missing.append("images")
            if not (p.description or "").strip():
                no_desc += 1
                missing.append("description")
            if not p.attributes:
                no_specs += 1
                missing.append("specs")
            if missing:
                rows.append([p.id, p.sku, p.name, p.brand, p.category.name if p.category else "", " ".join(missing), ""])

        self.stdout.write(f"Products: {total}")
        self.stdout.write(f"  without images:      {no_images}")
        self.stdout.write(f"  without description: {no_desc}")
        self.stdout.write(f"  without specs:       {no_specs}")
        self.stdout.write(f"  incomplete (any):    {len(rows)}")

        if opts["export"]:
            with open(opts["export"], "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["id", "sku", "name", "brand", "category", "missing", "url"])
                w.writerows(rows)
            self.stdout.write(self.style.SUCCESS(f"Exported {len(rows)} products to {opts['export']}. Fill the url column, then run scrape_product_details."))
