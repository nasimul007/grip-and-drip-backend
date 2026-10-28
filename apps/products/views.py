import random
from django.db.models import (
    Case, Count, DecimalField, Exists, F, IntegerField, Max, Min, OuterRef,
    Q, Subquery, Sum, Value, When,
)
from django.db.models.functions import Coalesce
from rest_framework import generics, filters, serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
import django_filters
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from .models import Brand, Product, ProductVariant, StockNotification
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    RelatedProductSerializer,
)
from apps.categories.models import Category


class ProductFilterSet(FilterSet):
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")
    on_sale = django_filters.BooleanFilter(method="filter_on_sale")
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

    def filter_in_stock(self, queryset, name, value):
        """Stock on the product itself or on any active variant."""
        has_variant_stock = Exists(
            ProductVariant.objects.filter(
                product=OuterRef("pk"), is_active=True, stock__gt=0
            )
        )
        in_stock = queryset.filter(Q(stock__gt=0) | has_variant_stock)
        return in_stock if value else queryset.exclude(pk__in=in_stock.values("pk"))

    def filter_on_sale(self, queryset, name, value):
        on_sale = Q(compare_price__isnull=False, compare_price__gt=F("price"))
        return queryset.filter(on_sale) if value else queryset.exclude(on_sale)

    def filter_category_with_descendants(self, queryset, name, value):
        if not value:
            return queryset
        query = Q()
        for cat in value:
            query |= cat.products_q()
        return queryset.filter(query)


def annotate_listing(queryset):
    """Adds discount_pct and sold so listings can be ordered by them."""
    from apps.orders.models import OrderItem

    sold = (
        OrderItem.objects.filter(product_slug=OuterRef("slug"))
        .exclude(order__status="cancelled")
        .values("product_slug")
        .annotate(total=Sum("quantity"))
        .values("total")
    )
    return queryset.annotate(
        discount_pct=Case(
            When(
                compare_price__isnull=False,
                compare_price__gt=F("price"),
                then=(F("compare_price") - F("price")) * 100 / F("compare_price"),
            ),
            default=Value(0),
            output_field=DecimalField(max_digits=7, decimal_places=2),
        ),
        sold=Coalesce(Subquery(sold, output_field=IntegerField()), Value(0)),
    )


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
    ordering_fields = [
        "price", "created_at", "name", "is_featured", "discount_pct", "sold",
    ]

    def get_queryset(self):
        return annotate_listing(super().get_queryset()).prefetch_related("variants", "images")

    def filter_queryset(self, queryset):
        """Apply filters/ordering, then list unavailable products last."""
        queryset = super().filter_queryset(queryset)
        has_variant_stock = Exists(
            ProductVariant.objects.filter(
                product=OuterRef("pk"), is_active=True, stock__gt=0
            )
        )
        ordering = list(queryset.query.order_by) or list(Product._meta.ordering)
        return queryset.annotate(
            unavailable=Case(
                When(Q(stock__gt=0) | has_variant_stock, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by("unavailable", *ordering)


class ProductFilterOptionsView(APIView):
    """
    Facets for the shop sidebar: brands with product counts and the price
    range. Computed over products matching the current category / search /
    stock / sale filters, but ignoring brand and price so those controls
    always show every choice.
    """

    def get(self, request):
        params = request.query_params.copy()
        for key in ("brand", "price__gte", "price__lte", "price"):
            params.pop(key, None)

        base = Product.objects.filter(is_active=True, soft_deleted=False)
        qs = ProductFilterSet(params, queryset=base).qs

        term = (params.get("search") or "").strip()
        if term:
            query = Q()
            for field in ProductListView.search_fields:
                query |= Q(**{f"{field}__icontains": term})
            qs = qs.filter(query)

        brands = (
            qs.exclude(brand="")
            .values("brand")
            .annotate(count=Count("id"))
            .order_by("-count", "brand")
        )
        price = qs.aggregate(min=Min("price"), max=Max("price"))
        logos = {
            b.name.lower(): request.build_absolute_uri(b.logo.url)
            for b in Brand.objects.exclude(logo="")
        }
        return Response(
            {
                "brands": [
                    {
                        "name": b["brand"],
                        "count": b["count"],
                        "logo": logos.get(b["brand"].lower()),
                    }
                    for b in brands
                ],
                "price": {
                    "min": int(price["min"] // 1) if price["min"] is not None else 0,
                    "max": int(-(-price["max"] // 1)) if price["max"] is not None else 0,
                },
                "count": qs.count(),
            }
        )


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
        ).exclude(pk=product.pk).prefetch_related("variants", "images")

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
        ).prefetch_related("variants", "images")


class StockNotifyThrottle(SimpleRateThrottle):
    scope = "stock_notify"
    rate = "20/hour"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


def _clean_contact(value: str) -> str:
    """A Bangladeshi mobile number (stored as 01XXXXXXXXX) or an email address."""
    value = (value or "").strip()
    try:
        validate_email(value)
        return value.lower()
    except DjangoValidationError:
        pass
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits.startswith("880"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("01"):
        return digits
    raise serializers.ValidationError(
        {"contact": "Enter a valid mobile number (01XXXXXXXXX) or email address."}
    )


class StockNotifyView(APIView):
    """Lets a shopper ask to be told when an out-of-stock product is available again."""

    permission_classes = (AllowAny,)
    throttle_classes = [StockNotifyThrottle]

    def post(self, request, slug):
        product = get_object_or_404(Product, slug=slug, is_active=True, soft_deleted=False)
        contact = _clean_contact(request.data.get("contact"))
        variant = None
        variant_id = request.data.get("variant_id")
        if variant_id:
            variant = get_object_or_404(
                ProductVariant, id=variant_id, product=product, is_active=True
            )
        available = variant.stock if variant is not None else product.total_stock
        if available > 0:
            return Response(
                {"detail": "This item is already in stock."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        StockNotification.objects.get_or_create(
            product=product, variant=variant, contact=contact
        )
        return Response(
            {"detail": "We will let you know when it is back in stock."},
            status=status.HTTP_201_CREATED,
        )
