from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import SimpleRateThrottle
from apps.products.models import Product, ProductVariant
from .models import (
    Cart, CartItem, Order, OrderItem, ShippingAddress, ShippingRate,
)
from .serializers import (
    CartSerializer, CartAddSerializer, CartItemUpdateSerializer,
    ShippingRateSerializer, OrderCreateSerializer,
    OrderListSerializer, OrderDetailSerializer,
)


class GuestOrderThrottle(SimpleRateThrottle):
    scope = "guest_order"

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return None
        ip = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ip}


class CartView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = CartSerializer

    def get_object(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return cart


class CartAddItemView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = CartAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = get_object_or_404(Product, id=serializer.validated_data["product_id"])
        variant = None
        variant_id = serializer.validated_data.get("variant_id")
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id)

        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={"quantity": serializer.validated_data["quantity"]},
        )
        if not created:
            cart_item.quantity += serializer.validated_data["quantity"]
            cart_item.save()

        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class CartItemUpdateView(APIView):
    permission_classes = (IsAuthenticated,)

    def patch(self, request, item_id):
        cart = get_object_or_404(Cart, user=request.user)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)

        serializer = CartItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart_item.quantity = serializer.validated_data["quantity"]
        cart_item.save()

        return Response(CartSerializer(cart).data)


class CartItemRemoveView(APIView):
    permission_classes = (IsAuthenticated,)

    def delete(self, request, item_id):
        cart = get_object_or_404(Cart, user=request.user)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        cart_item.delete()

        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class CartClearView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        cart = get_object_or_404(Cart, user=request.user)
        cart.items.all().delete()
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class ShippingRateListView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    queryset = ShippingRate.objects.filter(is_active=True)
    serializer_class = ShippingRateSerializer


class OrderCreateView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = [GuestOrderThrottle]

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        valid = serializer.validated_data
        shipping_rate = get_object_or_404(
            ShippingRate, id=valid["shipping_rate_id"]
        )

        # Anonymous/guest checkout: items come from the request body and are
        # validated + priced server-side (never trust client prices).
        if not request.user or not request.user.is_authenticated:
            items_data = valid.get("items")
            if not items_data:
                return Response(
                    {"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST
                )

            line_items = []
            for item in items_data:
                product = get_object_or_404(
                    Product, id=item["product_id"], is_active=True
                )
                variant = None
                variant_id = item.get("variant_id")
                if variant_id:
                    variant = get_object_or_404(
                        ProductVariant, id=variant_id, product=product
                    )
                line_items.append(
                    {
                        "product": product,
                        "variant": variant,
                        "quantity": item["quantity"],
                    }
                )

            if not line_items:
                return Response(
                    {"error": "No valid cart items."}, status=status.HTTP_400_BAD_REQUEST
                )

            return self._create_order(
                request,
                valid,
                shipping_rate,
                line_items,
                user=None,
            )

        # Authenticated: fall back to the user's server-side cart.
        cart_items = get_object_or_404(Cart, user=request.user).items.all()
        if not cart_items.exists():
            return Response(
                {"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST
            )

        line_items = [
            {
                "product": item.product,
                "variant": item.variant,
                "quantity": item.quantity,
            }
            for item in cart_items
        ]
        return self._create_order(
            request,
            valid,
            shipping_rate,
            line_items,
            user=request.user,
        )

    def _create_order(self, request, valid, shipping_rate, line_items, user):
        subtotal = sum(
            float(item["product"].effective_price) * item["quantity"]
            for item in line_items
        )

        shipping_cost = float(shipping_rate.charge)
        if (
            shipping_rate.free_shipping_minimum
            and subtotal >= float(shipping_rate.free_shipping_minimum)
        ):
            shipping_cost = 0

        total = subtotal + shipping_cost
        address_data = valid["shipping_address"]

        # Lock product/variant rows, validate availability, then create the
        # order and decrement stock atomically (race-safe, no overselling).
        with transaction.atomic():
            locked_lines = []
            for line in line_items:
                locked_product = Product.objects.select_for_update().get(
                    id=line["product"].id
                )
                variant = line["variant"]
                locked_variant = None
                if variant is not None:
                    locked_variant = ProductVariant.objects.select_for_update().get(
                        id=variant.id
                    )
                    available = locked_variant.stock
                else:
                    available = locked_product.stock

                quantity = line["quantity"]
                if quantity > available:
                    raise serializers.ValidationError(
                        {
                            "items": (
                                f"Insufficient stock for '{locked_product.name}'. "
                                f"Available: {available}, requested: {quantity}."
                            )
                        }
                    )
                locked_lines.append(
                    {
                        "product": locked_product,
                        "variant": locked_variant,
                        "quantity": quantity,
                    }
                )

            order = Order.objects.create(
                user=user,
                shipping_rate=shipping_rate,
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                total=total,
                notes=valid.get("notes", ""),
                payment_method=valid.get("payment_method", "cash"),
                payment_details=valid.get("payment_details", {}),
            )

            for line in locked_lines:
                product = line["product"]
                quantity = line["quantity"]
                variant = line["variant"]

                primary_image = product.images.filter(is_primary=True).first()
                image_url = primary_image.image.url if primary_image else ""
                if product.images.exists() and not image_url:
                    image_url = product.images.first().image.url

                OrderItem.objects.create(
                    order=order,
                    product_name=product.name,
                    product_slug=product.slug,
                    product_image=(
                        request.build_absolute_uri(image_url) if image_url else ""
                    ),
                    price=float(product.effective_price),
                    quantity=quantity,
                    variant_name=variant.name if variant else "",
                )

                # Decrement stock atomically (rows are locked + validated above,
                # so this cannot go negative).
                if variant is not None:
                    ProductVariant.objects.filter(pk=variant.pk).update(
                        stock=F("stock") - quantity
                    )
                else:
                    Product.objects.filter(pk=product.pk).update(
                        stock=F("stock") - quantity
                    )

            ShippingAddress.objects.create(
                order=order,
                full_name=address_data["full_name"],
                phone=address_data["phone"],
                address_line1=address_data["address_line1"],
                address_line2=address_data.get("address_line2", ""),
                city=address_data["city"],
                state=address_data.get("state", ""),
                country=address_data.get("country", "Bangladesh"),
            )

            if user is not None:
                user.cart.items.all().delete()

        return Response(
            OrderDetailSerializer(order).data, status=status.HTTP_201_CREATED
        )


class OrderListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = OrderListSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = OrderDetailSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)
