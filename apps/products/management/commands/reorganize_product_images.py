import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.products.models import Product, ProductImage, ProductVariant


class Command(BaseCommand):
    help = "Reorganize product images into product-slug-based subfolders"

    def handle(self, *args, **options):
        media = Path(settings.MEDIA_ROOT)
        images_dir = media / "products" / "images"
        og_dir = media / "products" / "og"
        variants_dir = media / "variants"

        moved_images = 0
        moved_og = 0
        moved_variants = 0
        errors = 0

        # ── A. ProductImage ──
        self.stdout.write("--- Product Images ---")
        for pi in ProductImage.objects.select_related("product").order_by(
            "product_id", "sort_order"
        ):
            old_rel = pi.image.name
            if not old_rel:
                continue
            slug = pi.product.slug
            old_path = media / old_rel
            if not old_path.exists():
                self.stderr.write(f"  MISSING: {old_rel} (ProductImage #{pi.id})")
                errors += 1
                continue

            ext = os.path.splitext(old_rel)[1] or ".jpg"
            target_dir = images_dir / slug
            target_dir.mkdir(parents=True, exist_ok=True)
            new_name = f"{pi.sort_order}{ext}"
            new_rel = f"products/images/{slug}/{new_name}"
            new_path = media / new_rel

            try:
                old_path.rename(new_path)
                pi.image.name = new_rel
                pi.save(update_fields=["image"])
                moved_images += 1
                self.stdout.write(f"  ✓ {slug}/{new_name}")
            except Exception as e:
                self.stderr.write(f"  ✗ {slug}/{new_name}: {e}")
                errors += 1

        # ── B. ProductVariant.image ──
        self.stdout.write("\n--- Variant Images ---")
        for v in ProductVariant.objects.select_related("product").exclude(image="").exclude(image__isnull=True):
            old_rel = v.image.name
            old_path = media / old_rel
            slug = v.product.slug
            if not old_path.exists():
                self.stderr.write(f"  MISSING: {old_rel} (Variant #{v.id})")
                errors += 1
                continue

            ext = os.path.splitext(old_rel)[1] or ".jpg"
            target_dir = variants_dir / slug
            target_dir.mkdir(parents=True, exist_ok=True)
            base_name = v.sku or f"variant-{v.id}"
            new_name = f"{base_name}{ext}"
            new_rel = f"variants/{slug}/{new_name}"
            new_path = media / new_rel

            try:
                old_path.rename(new_path)
                v.image.name = new_rel
                v.save(update_fields=["image"])
                moved_variants += 1
                self.stdout.write(f"  ✓ variants/{slug}/{new_name}")
            except Exception as e:
                self.stderr.write(f"  ✗ variants/{slug}/{new_name}: {e}")
                errors += 1

        # ── C. Product.og_image ──
        self.stdout.write("\n--- OG Images ---")
        for p in Product.objects.exclude(og_image="").exclude(og_image__isnull=True):
            old_rel = p.og_image.name
            if not old_rel:
                continue
            old_path = media / old_rel
            slug = p.slug
            if not old_path.exists():
                self.stderr.write(f"  MISSING: {old_rel} (Product #{p.id})")
                errors += 1
                continue

            ext = os.path.splitext(old_rel)[1] or ".jpg"
            target_dir = og_dir / slug
            target_dir.mkdir(parents=True, exist_ok=True)
            new_rel = f"products/og/{slug}/og{ext}"
            new_path = media / new_rel

            try:
                old_path.rename(new_path)
                p.og_image = new_rel
                p.save(update_fields=["og_image"])
                moved_og += 1
                self.stdout.write(f"  ✓ products/og/{slug}/og{ext}")
            except Exception as e:
                self.stderr.write(f"  ✗ products/og/{slug}/og{ext}: {e}")
                errors += 1

        # ── D. Cleanup empty flat dirs ──
        self.stdout.write("\n--- Cleanup ---")
        for flat_dir in [images_dir, og_dir, variants_dir]:
            if flat_dir.exists():
                remaining = list(flat_dir.iterdir())
                files = [f for f in remaining if f.is_file()]
                dirs = [f for f in remaining if f.is_dir()]
                if files:
                    self.stdout.write(f"  {flat_dir.name}/: {len(files)} leftover files")
                if dirs:
                    self.stdout.write(f"  {flat_dir.name}/: {len(dirs)} subdirectories (expected)")

        # ── Summary ──
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done! Moved: {moved_images} product images, "
                f"{moved_variants} variant images, "
                f"{moved_og} OG images. Errors: {errors}"
            )
        )
