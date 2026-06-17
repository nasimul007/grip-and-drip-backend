from rest_framework import serializers
from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "sort_order",
            "children",
        )

    def get_children(self, obj):
        children = obj.get_children().filter(is_active=True)
        return CategorySerializer(children, many=True).data


class CategoryBreadcrumbSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()


class CategoryDetailSerializer(serializers.ModelSerializer):
    breadcrumb = serializers.SerializerMethodField()
    subcategories = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "meta_title",
            "meta_description",
            "og_image",
            "is_active",
            "sort_order",
            "breadcrumb",
            "subcategories",
            "product_count",
        )

    def get_breadcrumb(self, obj):
        return obj.get_breadcrumb()

    def get_subcategories(self, obj):
        children = obj.get_children().filter(is_active=True)
        return CategorySerializer(children, many=True).data

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True, soft_deleted=False).count()
