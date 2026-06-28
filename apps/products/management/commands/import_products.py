import json
import os
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.categories.models import Category
from apps.products.models import Product, ProductVariant


class Command(BaseCommand):
    help = "Import products from the PDF-derived JSON data file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--data",
            type=str,
            default=os.path.join(os.path.dirname(__file__), "products_import_data.json"),
            help="Path to the JSON data file",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate without inserting into the database",
        )

    def handle(self, *args, **options):
        data_path = options["data"]
        dry_run = options["dry_run"]

        with open(data_path, "r") as f:
            products_data = json.load(f)

        self.stdout.write(f"Loaded {len(products_data)} products from {data_path}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be made"))

        stats = {"created": 0, "variants": 0, "skipped": 0, "errors": 0}

        for entry in products_data:
            try:
                self._import_product(entry, dry_run, stats)
            except Exception as e:
                stats["errors"] += 1
                self.stdout.write(
                    self.style.ERROR(f"  Error importing '{entry['name']}': {e}")
                )

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS(
            f"Summary: {stats['created']} products created, "
            f"{stats['variants']} variants, "
            f"{stats['skipped']} skipped, "
            f"{stats['errors']} errors"
        ))

    def _resolve_category(self, path, dry_run):
        if not path:
            return None

        parent = None
        for name in path:
            try:
                cat = Category.objects.get(name=name, parent=parent)
            except Category.DoesNotExist:
                if dry_run:
                    self.stdout.write(f"  [DRY RUN] Would create category: {name}")
                    cat = None
                else:
                    cat = Category.objects.create(
                        name=name,
                        parent=parent,
                    )
                    self.stdout.write(f"  Created category: {name}")
            parent = cat
        return parent

    def _import_product(self, entry, dry_run, stats):
        name = entry["name"]
        brand = entry.get("brand", "")
        sku = entry["sku"]
        wholesale = entry.get("wholesale_price")
        retail = entry.get("retail_price")
        stock = entry.get("stock", 0)
        warranty = entry.get("warranty") or ""
        colors = entry.get("colors", [])
        category_path = entry.get("category_path", [])
        note = entry.get("note", "")

        # Skip if product with this SKU already exists
        if Product.objects.filter(sku=sku).exists() and not dry_run:
            self.stdout.write(f"  Skipped (SKU exists): {name} ({sku})")
            stats["skipped"] += 1
            return

        category = self._resolve_category(category_path, dry_run)

        if dry_run:
            color_str = ", ".join(colors)
            self.stdout.write(
                f"  [DRY RUN] Would create: {name} | "
                f"Brand: {brand} | SKU: {sku} | "
                f"Price: {retail} | Colors: {color_str} | "
                f"Stock: {stock} | Category: {' > '.join(category_path)}"
            )
            if note:
                self.stdout.write(f"    Note: {note}")
            stats["created"] += 1
            stats["variants"] += len(colors) if len(colors) > 1 else 0
            return

        description_parts = []
        if warranty:
            description_parts.append(f"Warranty: {warranty}")
        if note:
            description_parts.append(note)
        description = ". ".join(description_parts) if description_parts else ""

        product = Product.objects.create(
            category=category,
            name=name,
            price=retail or 0,
            compare_price=None,
            sku=sku,
            stock=stock if len(colors) <= 1 else 0,
            brand=brand,
            is_active=True,
            description=description,
        )

        # Create variants for multi-color products
        if len(colors) > 1:
            for i, color in enumerate(colors):
                color_slug = slugify(color)[:3].upper()
                variant_sku = f"{sku}-{color_slug}"
                # Handle SKU collisions
                if ProductVariant.objects.filter(sku=variant_sku).exists():
                    variant_sku = f"{sku}-{color_slug}-{i+1}"

                ProductVariant.objects.create(
                    product=product,
                    name=color,
                    sku=variant_sku,
                    stock=stock,
                    is_active=True,
                    attributes={"Color": color},
                    sort_order=i,
                )
                stats["variants"] += 1
        elif len(colors) == 1:
            ProductVariant.objects.create(
                product=product,
                name=colors[0],
                sku=f"{sku}-{slugify(colors[0])[:3].upper()}",
                stock=stock,
                is_active=True,
                attributes={"Color": colors[0]},
                sort_order=0,
            )
            stats["variants"] += 1

        stats["created"] += 1
        self.stdout.write(f"  Created: {name} ({sku})")
