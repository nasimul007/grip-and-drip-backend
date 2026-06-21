from django.db import models
from django.conf import settings
from apps.products.models import Product, ProductVariant


class ShippingRate(models.Model):
    AREA_CHOICES = [
        ("inside_dhaka", "Inside Dhaka"),
        ("outside_dhaka", "Outside Dhaka"),
    ]

    area_type = models.CharField(max_length=20, choices=AREA_CHOICES, unique=True)
    charge = models.DecimalField(max_digits=10, decimal_places=2)
    free_shipping_minimum = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Shipping Rate"
        verbose_name_plural = "Shipping Rates"

    def __str__(self):
        return f"{self.get_area_type_display()} - {self.charge}"


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart ({self.user.email})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True
    )
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("cart", "product", "variant")

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders"
    )
    order_number = models.CharField(max_length=30, unique=True, editable=False)
    shipping_rate = models.ForeignKey(
        ShippingRate, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        if not self.order_number:
            from django.utils import timezone
            now = timezone.localtime(timezone.now())
            date_part = now.strftime("%Y%m%d")
            last_today = Order.objects.filter(
                order_number__startswith=f"ORD-{date_part}"
            ).count()
            self.order_number = f"ORD-{date_part}-{last_today + 1:04d}"
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product_name = models.CharField(max_length=255)
    product_slug = models.SlugField(max_length=255)
    product_image = models.URLField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    variant_name = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


class ShippingAddress(models.Model):
    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name="shipping_address"
    )
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="Bangladesh")

    def __str__(self):
        return f"{self.full_name} - {self.city}"
