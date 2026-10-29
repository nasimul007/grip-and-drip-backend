from django.db import models
from django.db.models import Q
from django.utils.text import slugify
from mptt.models import MPTTModel, TreeForeignKey
from ckeditor.fields import RichTextField
from config.html import clean_html


class Category(MPTTModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    parent = TreeForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    description = RichTextField(blank=True)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    og_image = models.ImageField(upload_to="categories/og/", blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class MPTTMeta:
        order_insertion_by = ["sort_order", "name"]

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        self.description = clean_html(self.description)
        super().save(*args, **kwargs)

    def _generate_unique_slug(self):
        base_slug = slugify(self.name)
        slug = base_slug
        counter = 1
        while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def get_breadcrumb(self):
        ancestors = self.get_ancestors(include_self=True)
        return [
            {"name": ancestor.name, "slug": ancestor.slug}
            for ancestor in ancestors
        ]

    def products_q(self):
        """
        Products listed under this category: everything in its subtree, plus
        products filed on an ancestor whose brand matches this category's
        name (e.g. Smartwatch > CMF shows CMF-brand products saved under
        Smartwatch).
        """
        q = Q(category__in=self.get_descendants(include_self=True))
        ancestors = self.get_ancestors()
        if ancestors:
            q |= Q(category__in=ancestors, brand__iexact=self.name)
        return q

    def get_meta_title(self):
        return self.meta_title or self.name

    def get_meta_description(self):
        return self.meta_description or (
            self.description[:157] + "..." if len(self.description) > 160 else self.description
        )


class CategoryFAQ(models.Model):
    """Question/answer shown on the category page (and as FAQ structured data)."""

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="faqs")
    question = models.CharField(max_length=255)
    answer = models.TextField(help_text="Plain text, 1-3 sentences.")
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "pk"]
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question
