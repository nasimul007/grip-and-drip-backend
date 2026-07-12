import random
from django.db.models import Q
from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
import django_filters
from .models import Product
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    RelatedProductSerializer,
)
from apps.categories.models import Category


class ProductFilterSet(FilterSet):
    category = django_filters.ModelMultipleChoiceFilter(
        queryset=Category.objects.all(),
        method='filter_category_with_descendants',
    )

    class Meta:
        model = Product
        fields = {
            "category__slug": ["exact"],
            "is_featured": ["exact"],
            "brand": ["exact"],
            "price": ["gte", "lte", "exact"],
        }

    def filter_category_with_descendants(self, queryset, name, value):
        if not value:
            return queryset
        all_ids = set()
        for cat in value:
            descendants = cat.get_descendants(include_self=True)
            all_ids.update(descendants.values_list('id', flat=True))
        return queryset.filter(category__in=all_ids)


class ProductListView(generics.ListAPIView):
    queryset = Product.objects.filter(is_active=True, soft_deleted=False)
    serializer_class = ProductListSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ProductFilterSet
    search_fields = ["name", "description", "sku", "brand"]
    ordering_fields = ["price", "created_at", "name", "is_featured"]


class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.filter(is_active=True, soft_deleted=False)
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"


class RelatedProductsView(generics.ListAPIView):
    serializer_class = RelatedProductSerializer

    def get_queryset(self):
        slug = self.kwargs.get("slug")
        try:
            product = Product.objects.get(
                slug=slug, is_active=True, soft_deleted=False
            )
        except Product.DoesNotExist:
            return Product.objects.none()

        related = Product.objects.filter(
            category=product.category,
            is_active=True,
            soft_deleted=False,
        ).exclude(pk=product.pk)

        related_list = list(related)
        random.shuffle(related_list)
        return related_list[:4]


class ProductSearchView(generics.ListAPIView):
    serializer_class = ProductListSerializer

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()
        if not q:
            return Product.objects.none()
        return Product.objects.filter(
            Q(is_active=True, soft_deleted=False)
            & (
                Q(name__icontains=q)
                | Q(description__icontains=q)
                | Q(sku__icontains=q)
                | Q(brand__icontains=q)
            )
        )
