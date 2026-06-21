from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem, ShippingAddress, ShippingRate


class CartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.SlugField(source="product.slug", read_only=True)
    product_image = serializers.SerializerMethodField()
    price = serializers.DecimalField(
        source="product.effective_price", max_digits=10, decimal_places=2, read_only=True
    )
    variant_name = serializers.CharField(
        source="variant.name", read_only=True, default=""
    )
    total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = (
            "id", "product_id", "product_name", "product_slug",
            "product_image", "price", "quantity", "variant_name", "total",
            "created_at",
        )

    def get_product_image(self, obj):
        primary = obj.product.images.filter(is_primary=True).first()
        if primary:
            return primary.image.url
        first = obj.product.images.first()
        return first.image.url if first else None

    def get_total(self, obj):
        return float(obj.product.effective_price) * obj.quantity


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ("id", "items", "total", "created_at", "updated_at")

    def get_total(self, obj):
        total = 0
        for item in obj.items.all():
            total += float(item.product.effective_price) * item.quantity
        return total


class CartAddSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(default=1, min_value=1)


class CartItemUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


class ShippingRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingRate
        fields = ("id", "area_type", "charge", "free_shipping_minimum")


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = (
            "full_name", "phone", "address_line1", "address_line2",
            "city", "state", "postal_code", "country",
        )


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "product_name", "product_slug", "product_image",
            "price", "quantity", "variant_name",
        )


class OrderListSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id", "order_number", "status", "subtotal",
            "shipping_cost", "total", "item_count", "created_at",
        )

    def get_item_count(self, obj):
        return obj.items.count()


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    shipping_address = ShippingAddressSerializer(read_only=True)
    shipping_area = serializers.CharField(
        source="shipping_rate.area_type", read_only=True, default=""
    )

    class Meta:
        model = Order
        fields = (
            "id", "order_number", "status", "subtotal",
            "shipping_cost", "total", "shipping_area", "notes",
            "items", "shipping_address", "created_at", "updated_at",
        )


class OrderCreateSerializer(serializers.Serializer):
    shipping_rate_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True)
    shipping_address = ShippingAddressSerializer()
