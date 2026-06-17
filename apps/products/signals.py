from django.core.cache import cache
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import Product

PRODUCT_CACHE_KEYS = [
    "product_list",
    "featured_products",
]


@receiver(pre_save, sender=Product)
def product_slug_handler(sender, instance, **kwargs):
    if not instance.slug:
        instance.slug = instance._generate_unique_slug()


@receiver([post_save, post_delete], sender=Product)
def product_cache_invalidation(sender, **kwargs):
    for key in PRODUCT_CACHE_KEYS:
        cache.delete(key)
