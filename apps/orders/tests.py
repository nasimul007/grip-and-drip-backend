from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.categories.models import Category
from apps.products.models import Product, ProductVariant

from .models import Cart, Order, OrderItem, ShippingRate

User = get_user_model()


class CartApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pass12345"
        )
        cls.category = Category.objects.create(name="Cables")
        cls.product = Product.objects.create(
            category=cls.category, name="USB Cable", price=Decimal("500"),
            sku="CAB-1", stock=5,
        )
        cls.variant = ProductVariant.objects.create(
            product=cls.product, name="2m", sku="CAB-1-2M",
            price_override=Decimal("450"), stock=3,
        )
        cls.other = Product.objects.create(
            category=cls.category, name="Charger", price=Decimal("900"),
            sku="CHG-1", stock=10,
        )
        cls.other_variant = ProductVariant.objects.create(
            product=cls.other, name="45W", sku="CHG-1-45", stock=4
        )

    def setUp(self):
        self.client.force_authenticate(self.user)

    def add(self, product, quantity=1, variant=None):
        body = {"product_id": product.id, "quantity": quantity}
        if variant is not None:
            body["variant_id"] = variant.id
        return self.client.post("/api/cart/add/", body, format="json")

    def test_add_merges_same_line_and_reports_stock(self):
        self.add(self.product, 2)
        res = self.add(self.product, 1)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["items"]), 1)
        item = res.data["items"][0]
        self.assertEqual(item["quantity"], 3)
        self.assertEqual(item["stock"], 5)
        self.assertIsNone(item["variant_id"])

    def test_add_is_capped_at_stock_with_warning(self):
        res = self.add(self.product, 9)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["items"][0]["quantity"], 5)
        self.assertIn("Only 5 available", res.data["warning"])

    def test_add_out_of_stock_is_rejected(self):
        Product.objects.filter(pk=self.other.pk).update(stock=0)
        res = self.add(self.other)
        self.assertEqual(res.status_code, 400)
        self.assertIn("out of stock", res.data["detail"])
        self.assertFalse(Cart.objects.filter(user=self.user, items__isnull=False).exists())

    def test_inactive_and_soft_deleted_products_cannot_be_added(self):
        Product.objects.filter(pk=self.product.pk).update(is_active=False)
        self.assertEqual(self.add(self.product).status_code, 404)
        Product.objects.filter(pk=self.product.pk).update(is_active=True, soft_deleted=True)
        self.assertEqual(self.add(self.product).status_code, 404)

    def test_variant_must_belong_to_product(self):
        res = self.add(self.product, 1, variant=self.other_variant)
        self.assertEqual(res.status_code, 404)

    def test_variant_override_price_is_used_in_cart(self):
        res = self.add(self.product, 2, variant=self.variant)
        item = res.data["items"][0]
        self.assertEqual(item["price"], 450.0)
        self.assertEqual(item["total"], 900.0)
        self.assertEqual(item["variant_id"], self.variant.id)
        self.assertEqual(item["stock"], 3)
        self.assertEqual(res.data["total"], 900.0)

    def test_update_quantity_is_capped_and_validated(self):
        item_id = self.add(self.product, 1).data["items"][0]["id"]
        res = self.client.patch(f"/api/cart/items/{item_id}/", {"quantity": 50}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["items"][0]["quantity"], 5)
        res = self.client.patch(f"/api/cart/items/{item_id}/", {"quantity": 0}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_delete_and_remove_endpoints_both_delete_the_item(self):
        first = self.add(self.product, 1).data["items"][0]["id"]
        second = self.add(self.other, 1).data["items"][-1]["id"]
        res = self.client.delete(f"/api/cart/items/{first}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual([i["id"] for i in res.data["items"]], [second])
        res = self.client.delete(f"/api/cart/items/{second}/remove/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["items"], [])
        self.assertEqual(self.client.get("/api/cart/").data["items"], [])

    def test_cannot_touch_another_users_cart_item(self):
        item_id = self.add(self.product, 1).data["items"][0]["id"]
        other_user = User.objects.create_user(
            username="x", email="x@example.com", password="pass12345"
        )
        self.client.force_authenticate(other_user)
        Cart.objects.get_or_create(user=other_user)
        self.assertEqual(self.client.delete(f"/api/cart/items/{item_id}/").status_code, 404)
        self.assertEqual(
            self.client.patch(f"/api/cart/items/{item_id}/", {"quantity": 2}, format="json").status_code, 404
        )


class OrderPricingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rate = ShippingRate.objects.create(
            area_type="inside_dhaka", charge=Decimal("60"),
            free_shipping_minimum=Decimal("3000"),
        )
        cls.product = Product.objects.create(
            name="Earbuds", price=Decimal("1000"), sku="EAR-1", stock=10
        )
        cls.variant = ProductVariant.objects.create(
            product=cls.product, name="White", sku="EAR-1-W",
            price_override=Decimal("800"), stock=5,
        )

    def order_body(self, items=None):
        body = {
            "shipping_rate_id": self.rate.id,
            "payment_method": "cash",
            "shipping_address": {
                "full_name": "Test Buyer", "phone": "01700000000",
                "address_line1": "House 1", "city": "Dhanmondi, Dhaka",
                "state": "Dhaka", "country": "Bangladesh",
            },
        }
        if items is not None:
            body["items"] = items
        return body

    def test_guest_order_uses_variant_override_price(self):
        res = self.client.post(
            "/api/orders/",
            self.order_body([{"product_id": self.product.id, "variant_id": self.variant.id, "quantity": 2}]),
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        order = Order.objects.get(pk=res.data["id"])
        self.assertEqual(order.subtotal, Decimal("1600"))
        self.assertEqual(order.total, Decimal("1660"))
        self.assertEqual(OrderItem.objects.get(order=order).price, Decimal("800"))
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 3)

    def test_user_order_matches_cart_total(self):
        user = User.objects.create_user(username="u", email="u@example.com", password="pass12345")
        self.client.force_authenticate(user)
        cart = self.client.post(
            "/api/cart/add/",
            {"product_id": self.product.id, "variant_id": self.variant.id, "quantity": 2},
            format="json",
        ).data
        res = self.client.post("/api/orders/", self.order_body(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(float(res.data["subtotal"]), cart["total"])
        self.assertEqual(self.client.get("/api/cart/").data["items"], [])

    def test_plain_product_still_uses_product_price(self):
        plain = Product.objects.create(name="Case", price=Decimal("300"), sku="CASE-1", stock=4)
        res = self.client.post(
            "/api/orders/",
            self.order_body([{"product_id": plain.id, "quantity": 1}]),
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Order.objects.get(pk=res.data["id"]).subtotal, Decimal("300"))


class CartImageTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.products.models import ProductImage

        cls.ProductImage = ProductImage
        cls.user = User.objects.create_user(
            username="imgbuyer", email="img@example.com", password="pass12345"
        )
        cls.category = Category.objects.create(name="Cases")
        cls.product = Product.objects.create(
            category=cls.category, name="Case", price=Decimal("300"), sku="CASE-1", stock=5,
        )
        cls.blue = ProductVariant.objects.create(
            product=cls.product, name="Blue", sku="CASE-1-B", stock=3, image="variants/blue.jpg",
        )
        cls.red = ProductVariant.objects.create(
            product=cls.product, name="Red", sku="CASE-1-R", stock=3,
        )

    def setUp(self):
        self.client.force_authenticate(self.user)

    def image_for(self, variant):
        self.client.delete("/api/cart/clear/")
        res = self.client.post(
            "/api/cart/add/",
            {"product_id": self.product.id, "variant_id": variant.id, "quantity": 1},
            format="json",
        )
        return res.data["items"][0]["product_image"]

    def test_variant_image_wins_over_product_image(self):
        self.ProductImage.objects.create(product=self.product, image="products/main.jpg", is_primary=True)
        self.assertTrue(self.image_for(self.blue).endswith("variants/blue.jpg"))

    def test_product_image_when_variant_has_none(self):
        self.ProductImage.objects.create(product=self.product, image="products/main.jpg", is_primary=True)
        self.assertTrue(self.image_for(self.red).endswith("products/main.jpg"))

    def test_other_variant_image_when_product_has_none(self):
        self.assertTrue(self.image_for(self.red).endswith("variants/blue.jpg"))

    def test_og_image_then_none(self):
        ProductVariant.objects.filter(pk=self.blue.pk).update(image="")
        self.assertIsNone(self.image_for(self.red))
        Product.objects.filter(pk=self.product.pk).update(og_image="og/case.jpg")
        self.assertTrue(self.image_for(self.red).endswith("og/case.jpg"))


class CartOrderTests(APITestCase):
    def test_lines_keep_their_order_when_quantity_changes(self):
        user = User.objects.create_user(username="ord", email="ord@example.com", password="pass12345")
        self.client.force_authenticate(user)
        products = [
            Product.objects.create(name=f"P{i}", price=Decimal("100"), sku=f"ORD-{i}", stock=9)
            for i in range(3)
        ]
        for p in products:
            self.client.post("/api/cart/add/", {"product_id": p.id, "quantity": 1}, format="json")
        before = [i["id"] for i in self.client.get("/api/cart/").data["items"]]
        for item_id in (before[0], before[-1], before[1]):
            res = self.client.patch(f"/api/cart/items/{item_id}/", {"quantity": 3}, format="json")
            self.assertEqual([i["id"] for i in res.data["items"]], before)
        self.assertEqual([i["id"] for i in self.client.get("/api/cart/").data["items"]], before)


class OrderTrackTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rate = ShippingRate.objects.create(area_type="inside_dhaka", charge=Decimal("60"))
        cls.product = Product.objects.create(name="Track Item", price=Decimal("500"), sku="TRK-1", stock=9)

    def place(self):
        res = self.client.post(
            "/api/orders/",
            {
                "shipping_rate_id": self.rate.id,
                "payment_method": "cash",
                "shipping_address": {
                    "full_name": "Rahim Uddin", "phone": "01712345678",
                    "address_line1": "House 1", "city": "Dhanmondi, Dhaka",
                    "state": "Dhaka", "country": "Bangladesh",
                },
                "items": [{"product_id": self.product.id, "quantity": 2}],
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        return res.data

    def track(self, number, phone):
        return self.client.post("/api/orders/track/", {"order_number": number, "phone": phone}, format="json")

    def test_phone_formats_match_and_response_hides_private_data(self):
        order = self.place()
        self.assertEqual(order["payment_method"], "cash")
        for phone in ("01712345678", "+8801712345678", "880 1712-345678"):
            res = self.track(order["order_number"].lower(), phone)
            self.assertEqual(res.status_code, 200, phone)
        self.assertEqual(res.data["customer_name"], "Rahim")
        self.assertEqual(res.data["status"], "pending")
        self.assertEqual(len(res.data["items"]), 1)
        self.assertNotIn("phone", str(res.data))
        self.assertNotIn("address_line1", res.data)

    def test_wrong_phone_and_unknown_order_look_the_same(self):
        order = self.place()
        wrong = self.track(order["order_number"], "01799999999")
        unknown = self.track("ORD-19990101-0001", "01712345678")
        short = self.track(order["order_number"], "123")
        self.assertEqual((wrong.status_code, unknown.status_code, short.status_code), (404, 404, 404))
        self.assertEqual(wrong.data, unknown.data)

    def test_status_label_and_steps_follow_the_model(self):
        order = self.place()
        Order.objects.filter(order_number=order["order_number"]).update(status="shipped")
        res = self.track(order["order_number"], "01712345678")
        self.assertEqual(res.data["status_display"], "Shipped")
        self.assertEqual(
            [s["key"] for s in res.data["status_steps"]],
            ["pending", "confirmed", "processing", "shipped", "delivered"],
        )
