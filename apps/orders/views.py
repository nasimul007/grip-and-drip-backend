from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from apps.products.models import Product, ProductVariant
from .models import Cart, CartItem, Order, OrderItem, ShippingRate
from .serializers import (
    CartSerializer, CartAddSerializer, CartItemUpdateSerializer,
    ShippingRateSerializer, OrderCreateSerializer,
    OrderListSerializer, OrderDetailSerializer,
)


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
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart = get_object_or_404(Cart, user=request.user)
        cart_items = cart.items.all()
        if not cart_items.exists():
            return Response(
                {"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST
            )

        shipping_rate = get_object_or_404(
            ShippingRate, id=serializer.validated_data["shipping_rate_id"]
        )

        subtotal = sum(
            float(item.product.effective_price) * item.quantity for item in cart_items
        )

        shipping_cost = float(shipping_rate.charge)
        if (
            shipping_rate.free_shipping_minimum
            and subtotal >= float(shipping_rate.free_shipping_minimum)
        ):
            shipping_cost = 0

        total = subtotal + shipping_cost
        address_data = serializer.validated_data["shipping_address"]

        order = Order.objects.create(
            user=request.user,
            shipping_rate=shipping_rate,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            total=total,
            notes=serializer.validated_data.get("notes", ""),
        )

        for cart_item in cart_items:
            product = cart_item.product
            primary_image = product.images.filter(is_primary=True).first()
            image_url = primary_image.image.url if primary_image else ""
            if product.images.exists() and not image_url:
                image_url = product.images.first().image.url

            OrderItem.objects.create(
                order=order,
                product_name=product.name,
                product_slug=product.slug,
                product_image=request.build_absolute_uri(image_url) if image_url else "",
                price=float(product.effective_price),
                quantity=cart_item.quantity,
                variant_name=cart_item.variant.name if cart_item.variant else "",
            )

        from .models import ShippingAddress
        ShippingAddress.objects.create(
            order=order,
            full_name=address_data["full_name"],
            phone=address_data["phone"],
            address_line1=address_data["address_line1"],
            address_line2=address_data.get("address_line2", ""),
            city=address_data["city"],
            state=address_data.get("state", ""),
            postal_code=address_data["postal_code"],
            country=address_data.get("country", "Bangladesh"),
        )

        cart.items.all().delete()

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
