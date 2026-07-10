import os
import urllib.request
from pathlib import Path
from decimal import Decimal

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from apps.products.models import Product, ProductImage, ProductVariant


class Command(BaseCommand):
    help = "Populate product with images, description, and SEO fields"

    def add_arguments(self, parser):
        parser.add_argument("product_id", type=int)
        parser.add_argument("--images", nargs="+", help="Image URLs to download")
        parser.add_argument("--desc", type=str, default="", help="Description HTML")
        parser.add_argument("--meta-title", type=str, default="")
        parser.add_argument("--meta-desc", type=str, default="")
        parser.add_argument("--skip-desc", action="store_true")

    def handle(self, *args, **options):
        pid = options["product_id"]
        image_urls = options.get("images") or []
        desc_html = options.get("desc") or ""
        meta_title = options.get("meta_title") or ""
        meta_desc = options.get("meta_desc") or ""
        skip_desc = options.get("skip_desc")

        try:
            product = Product.objects.get(id=pid)
        except Product.DoesNotExist:
            self.stderr.write(f"Product ID {pid} not found")
            return

        base_slug = product.slug or slugify(product.name)
        images_subdir = Path(settings.MEDIA_ROOT) / "products" / "images" / base_slug
        og_subdir = Path(settings.MEDIA_ROOT) / "products" / "og" / base_slug
        images_subdir.mkdir(parents=True, exist_ok=True)
        og_subdir.mkdir(parents=True, exist_ok=True)

        downloaded = []

        for i, url in enumerate(image_urls):
            ext = self._guess_ext(url)
            filename = f"{i}{ext}"
            filepath = images_subdir / filename
            rel = f"products/images/{base_slug}/{filename}"

            self.stdout.write(f"  [{i+1}/{len(image_urls)}] Downloading {url[:80]}... ", ending="")
            try:
                urllib.request.urlretrieve(url, filepath)
                size = filepath.stat().st_size
                self.stdout.write(f"OK ({size}b)")

                img = ProductImage.objects.create(
                    product=product,
                    image=rel,
                    alt_text=f"{product.name} - View {i+1}",
                    is_primary=(i == 0),
                    sort_order=i,
                )
                downloaded.append((filename, filepath))
                self.stdout.write(f"    -> ProductImage #{img.id}")
            except Exception as e:
                self.stdout.write(f"FAILED: {e}")

        if downloaded:
            primary_filename, primary_path = downloaded[0]
            og_path = og_subdir / f"og{Path(primary_filename).suffix or '.jpg'}"
            og_rel = f"products/og/{base_slug}/og{Path(primary_filename).suffix or '.jpg'}"
            try:
                import shutil
                shutil.copy2(primary_path, og_path)
                product.og_image = og_rel
                self.stdout.write(f"  og_image set to {og_rel}")
            except Exception as e:
                self.stderr.write(f"  og_image copy failed: {e}")

        # Update description if provided
        if desc_html:
            product.description = desc_html
            self.stdout.write("  Description updated")

        # Set SEO fields (auto-generate if not provided)
        product.meta_title = meta_title or f"{product.name} | Gadget & Widget"
        if meta_desc:
            product.meta_description = meta_desc
        elif product.description:
            plain = product.description.replace("<p>", "").replace("</p>", "\n").replace("<br>", "\n").replace("<li>", "- ").replace("</li>", "\n").replace("<ul>", "").replace("</ul>", "").replace("<strong>", "").replace("</strong>", "")
            import re
            plain = re.sub(r"<[^>]+>", "", plain).strip()
            product.meta_description = plain[:157]

        product.save()
        self.stdout.write(f"  meta_title: {product.meta_title}")
        self.stdout.write(f"  meta_description: {product.meta_description[:80]}...")

        # Update first variant image
        variant = product.variants.filter(is_active=True).first()
        if variant and downloaded:
            variant.image = f"products/images/{base_slug}/{downloaded[0][0]}"
            variant.save()
            self.stdout.write(f"  Variant '{variant.name}' image updated")

        self.stdout.write(self.style.SUCCESS(f"Product ID {pid} ({product.name}) done!"))

    def _guess_ext(self, url):
        url = url.split("?")[0].split("#")[0]
        if url.endswith(".png") or "png-alpha" in url or "png" in url.lower():
            return ".png"
        if url.endswith(".webp"):
            return ".webp"
        return ".jpg"
