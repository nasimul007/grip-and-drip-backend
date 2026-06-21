from django.contrib import admin
from .models import ShippingRate, Cart, CartItem, Order, OrderItem, ShippingAddress


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    list_display = ("area_type", "charge", "free_shipping_minimum", "is_active")
    list_filter = ("is_active",)


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ("product", "variant", "quantity")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "item_count", "created_at")
    inlines = [CartItemInline]

    def item_count(self, obj):
        return obj.items.count()


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_name", "product_slug", "price", "quantity")


class ShippingAddressInline(admin.StackedInline):
    model = ShippingAddress


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number", "user", "status", "subtotal",
        "shipping_cost", "total", "created_at"
    )
    list_filter = ("status", "created_at")
    search_fields = ("order_number", "user__email", "user__username")
    inlines = [OrderItemInline, ShippingAddressInline]
    readonly_fields = (
        "order_number", "subtotal", "shipping_cost", "total"
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("product_name", "order", "price", "quantity")
    search_fields = ("product_name",)


@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "city", "order")
    search_fields = ("full_name", "phone")
