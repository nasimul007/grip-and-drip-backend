from django.contrib import admin
from mptt.admin import DraggableMPTTAdmin
from .models import Category


@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    list_display = (
        "tree_actions",
        "indented_title",
        "slug",
        "is_active",
        "sort_order",
        "product_count",
    )
    list_display_links = ("indented_title",)
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    mptt_level_indent = 20

    def product_count(self, obj):
        return obj.products.count()

    product_count.short_description = "Products"
