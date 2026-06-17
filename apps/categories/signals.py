from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Category


@receiver(pre_save, sender=Category)
def category_slug_handler(sender, instance, **kwargs):
    if not instance.slug:
        instance.slug = instance._generate_unique_slug()
