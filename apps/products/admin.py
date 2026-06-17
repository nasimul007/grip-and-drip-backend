from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import Product, ProductImage, ProductVariant, Attribute, AttributeValue


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "alt_text", "is_primary", "sort_order", "image_preview")
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 60px; max-width: 60px;" />',
                obj.image.url,
            )
        return ""

    image_preview.short_description = "Preview"


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ("name", "sku", "price_override", "stock", "is_active", "attributes")


class ProductResource(resources.ModelResource):
    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "category__name",
            "price",
            "compare_price",
            "sku",
            "stock",
            "is_active",
            "is_featured",
            "brand",
        )


@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = ProductResource
    list_display = (
        "thumbnail_preview",
        "name",
        "category",
        "price",
        "stock",
        "is_active",
        "is_featured",
        "created_at",
    )
    list_display_links = ("thumbnail_preview", "name")
    list_filter = ("is_active", "is_featured", "category", "brand")
    search_fields = ("name", "sku", "brand")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline, ProductVariantInline]
    actions = ["activate_products", "deactivate_products", "regenerate_slugs"]
    fieldsets = (
        (
            "Basic Info",
            {
                "fields": (
                    "name",
                    "slug",
                    "category",
                    "description",
                    "brand",
                    "sku",
                )
            },
        ),
        (
            "Pricing & Inventory",
            {"fields": ("price", "compare_price", "stock", "is_active", "is_featured")},
        ),
        (
            "SEO",
            {
                "fields": (
                    "meta_title",
                    "meta_description",
                    "og_image",
                )
            },
        ),
        (
            "Additional",
            {"fields": ("attributes", "soft_deleted"), "classes": ("collapse",)},
        ),
    )

    def thumbnail_preview(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if primary and primary.image:
            return format_html(
                '<img src="{}" style="max-height: 40px; max-width: 40px;" />',
                primary.image.url,
            )
        return "—"

    thumbnail_preview.short_description = "Image"

    def activate_products(self, request, queryset):
        queryset.update(is_active=True)

    activate_products.short_description = "Activate selected products"

    def deactivate_products(self, request, queryset):
        queryset.update(is_active=False)

    deactivate_products.short_description = "Deactivate selected products"

    def regenerate_slugs(self, request, queryset):
        for product in queryset:
            product.save()

    regenerate_slugs.short_description = "Regenerate slugs for selected products"


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "alt_text", "is_primary", "sort_order", "image_preview")
    list_filter = ("is_primary",)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 60px; max-width: 60px;" />',
                obj.image.url,
            )
        return ""

    image_preview.short_description = "Preview"


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("product", "name", "sku", "price_override", "stock", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "sku")


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(AttributeValue)
class AttributeValueAdmin(admin.ModelAdmin):
    list_display = ("attribute", "value", "slug")
    list_filter = ("attribute",)
    prepopulated_fields = {"slug": ("value",)}
