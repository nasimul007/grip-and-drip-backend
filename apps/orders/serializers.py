from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem, ShippingAddress, ShippingRate
from .pricing import available_stock, unit_price


class CartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.SlugField(source="product.slug", read_only=True)
    product_image = serializers.SerializerMethodField()
    variant_id = serializers.IntegerField(source="variant.id", read_only=True, default=None)
    variant_name = serializers.CharField(
        source="variant.name", read_only=True, default=""
    )
    price = serializers.SerializerMethodField()
    compare_price = serializers.SerializerMethodField()
    stock = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = (
            "id", "product_id", "product_name", "product_slug",
            "product_image", "variant_id", "variant_name", "price",
            "compare_price", "stock", "quantity", "total", "created_at",
        )

    def get_product_image(self, obj):
        primary = obj.product.images.filter(is_primary=True).first()
        if primary:
            return primary.image.url
        first = obj.product.images.first()
        return first.image.url if first else None

    def get_price(self, obj):
        return float(unit_price(obj.product, obj.variant))

    def get_compare_price(self, obj):
        compare = obj.product.compare_price
        if compare is not None and float(compare) > self.get_price(obj):
            return float(compare)
        return None

    def get_stock(self, obj):
        return available_stock(obj.product, obj.variant)

    def get_total(self, obj):
        return self.get_price(obj) * obj.quantity


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ("id", "items", "total", "created_at", "updated_at")

    def get_total(self, obj):
        return sum(
            float(unit_price(item.product, item.variant)) * item.quantity
            for item in obj.items.select_related("product", "variant")
        )


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
            "city", "state", "country",
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


class OrderCreateItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1)


class OrderCreateSerializer(serializers.Serializer):
    shipping_rate_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True)
    shipping_address = ShippingAddressSerializer()
    payment_method = serializers.ChoiceField(
        choices=["cash", "bkash", "bank"], default="cash"
    )
    payment_details = serializers.JSONField(required=False)
    items = OrderCreateItemSerializer(many=True, required=False)
