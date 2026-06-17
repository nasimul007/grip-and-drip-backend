from rest_framework import serializers
from .models import Product, ProductImage, ProductVariant


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "image", "alt_text", "is_primary", "sort_order")


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "name",
            "sku",
            "price_override",
            "stock",
            "is_active",
            "attributes",
            "sort_order",
        )


class ProductListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_slug = serializers.CharField(source="category.slug", read_only=True)
    effective_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "primary_image",
            "category_name",
            "category_slug",
            "price",
            "compare_price",
            "effective_price",
            "stock",
            "is_active",
            "is_featured",
            "brand",
            "created_at",
        )

    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            return ProductImageSerializer(primary).data
        first_img = obj.images.first()
        if first_img:
            return ProductImageSerializer(first_img).data
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_slug = serializers.CharField(source="category.slug", read_only=True)
    effective_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    breadcrumb = serializers.SerializerMethodField()
    schema_markup = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "category_name",
            "category_slug",
            "price",
            "compare_price",
            "effective_price",
            "sku",
            "stock",
            "is_active",
            "is_featured",
            "brand",
            "attributes",
            "meta_title",
            "meta_description",
            "og_image",
            "images",
            "variants",
            "breadcrumb",
            "schema_markup",
            "created_at",
            "updated_at",
        )

    def get_breadcrumb(self, obj):
        if obj.category:
            return obj.category.get_breadcrumb()
        return []

    def get_schema_markup(self, obj):
        request = self.context.get("request")
        return generate_product_schema(obj, request)


class RelatedProductSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    effective_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "primary_image",
            "price",
            "compare_price",
            "effective_price",
            "stock",
            "brand",
        )

    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            return ProductImageSerializer(primary).data
        first_img = obj.images.first()
        if first_img:
            return ProductImageSerializer(first_img).data
        return None


from apps.seo.schema import product_schema as _product_schema


def generate_product_schema(product, request=None):
    return _product_schema(product, request)
