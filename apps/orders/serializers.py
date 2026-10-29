from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem, ShippingAddress, ShippingRate
from .pricing import available_stock, cart_line_image, unit_price


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
        return cart_line_image(obj.product, obj.variant)

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
    items = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ("id", "items", "total", "created_at", "updated_at")

    def get_items(self, obj):
        # Fixed order (oldest first) so editing a line never moves it.
        items = obj.items.select_related("product", "variant").order_by("created_at", "id")
        return CartItemSerializer(items, many=True, context=self.context).data

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


class StatusFieldsMixin(serializers.Serializer):
    """status_display = the label admins see; status_steps = the order's normal path."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    status_steps = serializers.SerializerMethodField()

    def get_status_steps(self, obj):
        return Order.status_steps()


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "product_name", "product_slug", "product_image",
            "price", "quantity", "variant_name",
        )


class OrderListSerializer(StatusFieldsMixin, serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id", "order_number", "status", "status_display", "status_steps",
            "subtotal", "shipping_cost", "total", "item_count", "created_at",
        )

    def get_item_count(self, obj):
        return obj.items.count()


class OrderDetailSerializer(StatusFieldsMixin, serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    shipping_address = ShippingAddressSerializer(read_only=True)
    shipping_area = serializers.CharField(
        source="shipping_rate.area_type", read_only=True, default=""
    )

    class Meta:
        model = Order
        fields = (
            "id", "order_number", "status", "status_display", "status_steps",
            "subtotal", "shipping_cost", "total", "shipping_area", "payment_method", "notes",
            "items", "shipping_address", "created_at", "updated_at",
        )


class OrderCreateItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1)


class OrderCreateSerializer(serializers.Serializer):
    shipping_rate_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    shipping_address = ShippingAddressSerializer()
    payment_method = serializers.ChoiceField(
        choices=["cash", "bkash", "bank"], default="cash"
    )
    payment_details = serializers.DictField(
        child=serializers.CharField(max_length=100, allow_blank=True),
        required=False,
    )
    items = OrderCreateItemSerializer(many=True, required=False, max_length=50)

    def validate_payment_details(self, value):
        if len(value) > 5:
            raise serializers.ValidationError("Too many payment fields.")
        return value


class OrderTrackSerializer(StatusFieldsMixin, serializers.ModelSerializer):
    """What a guest may see after proving they know the order number and phone."""

    items = OrderItemSerializer(many=True, read_only=True)
    shipping_area = serializers.CharField(
        source="shipping_rate.area_type", read_only=True, default=""
    )
    customer_name = serializers.SerializerMethodField()
    delivery_area = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "order_number", "status", "status_display", "status_steps",
            "payment_method", "subtotal",
            "shipping_cost", "total", "shipping_area", "customer_name",
            "delivery_area", "items", "created_at", "updated_at",
        )

    def get_customer_name(self, obj):
        address = getattr(obj, "shipping_address", None)
        return address.full_name.split(" ")[0] if address and address.full_name else ""

    def get_delivery_area(self, obj):
        address = getattr(obj, "shipping_address", None)
        return address.city if address else ""


class OrderTrackRequestSerializer(serializers.Serializer):
    order_number = serializers.CharField(max_length=30)
    phone = serializers.CharField(max_length=30)
