import random
from django.db.models import Q
from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Product
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    RelatedProductSerializer,
)


class ProductListView(generics.ListAPIView):
    queryset = Product.objects.filter(is_active=True, soft_deleted=False)
    serializer_class = ProductListSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        "category": ["exact"],
        "category__slug": ["exact"],
        "is_featured": ["exact"],
        "brand": ["exact"],
        "price": ["gte", "lte", "exact"],
    }
    search_fields = ["name", "description", "sku", "brand"]
    ordering_fields = ["price", "created_at", "name"]


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
