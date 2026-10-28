from rest_framework import serializers
from .models import Review, Product, ProductImage, ProductVariant


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
            "image",
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

    total_stock = serializers.IntegerField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)
    rating_average = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    def get_rating_average(self, obj):
        return obj.review_stats()[0]

    def get_review_count(self, obj):
        return obj.review_stats()[1]

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "primary_image",
            "rating_average",
            "review_count",
            "category_name",
            "category_slug",
            "price",
            "compare_price",
            "effective_price",
            "stock",
            "total_stock",
            "in_stock",
            "is_active",
            "is_featured",
            "brand",
            "warranty_months",
            "created_at",
        )

    def get_primary_image(self, obj):
        found = obj.display_image()
        if not found:
            return None
        image, pk, is_primary = found
        # Relative media URL, as the previous ProductImageSerializer output (no request context).
        return {"id": pk, "image": image.url, "alt_text": obj.name, "is_primary": is_primary, "sort_order": 0}


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
    rating_average = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    def get_rating_average(self, obj):
        return obj.review_stats()[0]

    def get_review_count(self, obj):
        return obj.review_stats()[1]

    total_stock = serializers.IntegerField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)

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
            "total_stock",
            "in_stock",
            "is_active",
            "is_featured",
            "brand",
            "warranty_months",
            "attributes",
            "meta_title",
            "meta_description",
            "og_image",
            "images",
            "variants",
            "breadcrumb",
            "schema_markup",
            "rating_average",
            "review_count",
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

    total_stock = serializers.IntegerField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)

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
            "total_stock",
            "in_stock",
            "brand",
            "warranty_months",
        )

    def get_primary_image(self, obj):
        found = obj.display_image()
        if not found:
            return None
        image, pk, is_primary = found
        # Relative media URL, as the previous ProductImageSerializer output (no request context).
        return {"id": pk, "image": image.url, "alt_text": obj.name, "is_primary": is_primary, "sort_order": 0}


from apps.seo.schema import product_schema as _product_schema


def generate_product_schema(product, request=None):
    return _product_schema(product, request)


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ("id", "reviewer_name", "rating", "title", "body", "created_at")


class ReviewCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    title = serializers.CharField(max_length=120, required=False, allow_blank=True)
    body = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    order_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
