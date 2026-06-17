from django.core.cache import cache
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import Category

CATEGORY_CACHE_KEYS = [
    "category_tree",
    "category_list",
]


@receiver(pre_save, sender=Category)
def category_slug_handler(sender, instance, **kwargs):
    if not instance.slug:
        instance.slug = instance._generate_unique_slug()


@receiver([post_save, post_delete], sender=Category)
def category_cache_invalidation(sender, **kwargs):
    for key in CATEGORY_CACHE_KEYS:
        cache.delete(key)
