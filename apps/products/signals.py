from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db.models import Value
from django.db.models.functions import Replace
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from .models import Product, ProductImage, ProductVariant

PRODUCT_CACHE_KEYS = [
    "product_list",
    "featured_products",
]


@receiver(pre_save, sender=Product)
def product_slug_handler(sender, instance, **kwargs):
    if not instance.slug:
        instance.slug = instance._generate_unique_slug()
        return

    if not instance.pk:
        return

    try:
        old = sender.objects.only("slug").get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.slug == instance.slug:
        return

    old_slug, new_slug = old.slug, instance.slug

    for sub in ("products/images", "products/og", "variants"):
        old_dir = Path(settings.MEDIA_ROOT) / sub / old_slug
        new_dir = Path(settings.MEDIA_ROOT) / sub / new_slug
        if old_dir.exists():
            old_dir.rename(new_dir)

    ProductImage.objects.filter(
        product=instance,
        image__startswith=f"products/images/{old_slug}/",
    ).update(
        image=Replace(
            "image",
            Value(f"products/images/{old_slug}/"),
            Value(f"products/images/{new_slug}/"),
        )
    )

    for prefix in ("products/images/", "variants/"):
        ProductVariant.objects.filter(
            product=instance,
            image__startswith=f"{prefix}{old_slug}/",
        ).update(
            image=Replace(
                "image",
                Value(f"{prefix}{old_slug}/"),
                Value(f"{prefix}{new_slug}/"),
            )
        )

    if instance.og_image and instance.og_image.name.startswith(
        f"products/og/{old_slug}/"
    ):
        instance.og_image.name = instance.og_image.name.replace(
            f"products/og/{old_slug}/", f"products/og/{new_slug}/", 1
        )


@receiver([post_save, post_delete], sender=Product)
def product_cache_invalidation(sender, **kwargs):
    for key in PRODUCT_CACHE_KEYS:
        cache.delete(key)
