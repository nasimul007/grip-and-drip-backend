import random
from django.db.models import (
    Avg, Case, Count, DecimalField, Exists, F, IntegerField, Max, Min, OuterRef,
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
from .models import Brand, Product, ProductVariant, Review, StockNotification
from .serializers import (
    ReviewCreateSerializer,
    ReviewSerializer,
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
    approved = Review.objects.filter(product=OuterRef("pk"), is_approved=True).values("product")
    return queryset.annotate(
        review_count=Coalesce(
            Subquery(approved.annotate(c=Count("id")).values("c"), output_field=IntegerField()),
            Value(0),
        ),
        rating_avg=Subquery(
            approved.annotate(a=Avg("rating")).values("a"), output_field=DecimalField(max_digits=3, decimal_places=2)
        ),
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
        brand_info = {b.name.lower(): b for b in Brand.objects.all()}
        return Response(
            {
                "brands": [
                    {
                        "name": b["brand"],
                        "count": b["count"],
                        "logo": (
                            request.build_absolute_uri(info.logo.url)
                            if (info := brand_info.get(b["brand"].lower())) and info.logo
                            else None
                        ),
                        "description": info.description if info else "",
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
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return annotate_listing(Product.objects.filter(is_active=True, soft_deleted=False))


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


class ReviewThrottle(SimpleRateThrottle):
    scope = "review_post"
    rate = "20/hour"

    def get_cache_key(self, request, view):
        if request.method != "POST":
            return None
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


def _reviewer_name(address) -> str:
    """First name plus last initial, e.g. "Rahim U."."""
    parts = (address.full_name if address else "").split()
    if not parts:
        return "Customer"
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0]}."


class ProductReviewsView(APIView):
    """Approved reviews of a product; verified buyers (delivered order) may add one."""

    permission_classes = (AllowAny,)
    throttle_classes = [ReviewThrottle]

    def get(self, request, slug):
        product = get_object_or_404(Product, slug=slug, is_active=True, soft_deleted=False)
        average, count = product.review_stats()
        reviews = product.reviews.filter(is_approved=True)[:50]
        return Response(
            {
                "average": average,
                "count": count,
                "results": ReviewSerializer(reviews, many=True).data,
            }
        )

    def post(self, request, slug):
        from apps.orders.models import Order
        from apps.orders.views import _phone_digits

        product = get_object_or_404(Product, slug=slug, is_active=True, soft_deleted=False)
        data = ReviewCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        valid = data.validated_data

        orders = Order.objects.filter(
            status="delivered", items__product_slug=product.slug
        ).select_related("shipping_address").distinct()
        number = (valid.get("order_number") or "").strip().upper()
        if request.user.is_authenticated:
            orders = orders.filter(user=request.user)
            if number:
                orders = orders.filter(order_number=number)
        else:
            phone = _phone_digits(valid.get("phone") or "")
            if not number or len(phone) < 10:
                raise serializers.ValidationError(
                    {"detail": "Enter your order number and the phone number used at checkout."}
                )
            orders = orders.filter(order_number=number)
            orders = [o for o in orders if getattr(o, "shipping_address", None) and _phone_digits(o.shipping_address.phone) == phone]

        # One review per delivered order and product.
        reviewed = set(Review.objects.filter(product=product).values_list("order_id", flat=True))
        order = next((o for o in orders if o.id not in reviewed), None)
        if order is None:
            raise serializers.ValidationError(
                {"detail": "We could not find a delivered order for this product that you have not reviewed yet."}
            )

        Review.objects.create(
            product=product,
            order=order,
            user=request.user if request.user.is_authenticated else None,
            reviewer_name=_reviewer_name(getattr(order, "shipping_address", None)),
            rating=valid["rating"],
            title=valid.get("title", ""),
            body=valid.get("body", ""),
        )
        return Response(
            {"detail": "Thank you! Your review will appear after we approve it."},
            status=status.HTTP_201_CREATED,
        )
