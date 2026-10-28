from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.categories.models import Category
from apps.orders.models import Order, OrderItem

from .models import Product, ProductVariant


class ShopListingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name="Audio")
        cls.anker_deal = Product.objects.create(
            category=cat, name="Anker Cable", price=Decimal("400"), compare_price=Decimal("500"),
            sku="A1", stock=5, brand="Anker",
        )
        cls.jbl_big_deal = Product.objects.create(
            category=cat, name="JBL Speaker", price=Decimal("1000"), compare_price=Decimal("2000"),
            sku="J1", stock=3, brand="JBL",
        )
        cls.jbl_out = Product.objects.create(
            category=cat, name="JBL Earbuds", price=Decimal("3000"), sku="J2", stock=0, brand="JBL",
        )
        # No stock on the product itself, but an active variant has stock.
        cls.variant_only = Product.objects.create(
            category=cat, name="Case", price=Decimal("200"), sku="C1", stock=0, brand="Baseus",
        )
        ProductVariant.objects.create(product=cls.variant_only, name="Red", sku="C1-R", stock=4)
        cls.inactive_variant_only = Product.objects.create(
            category=cat, name="Old Case", price=Decimal("150"), sku="C2", stock=0, brand="Baseus",
        )
        ProductVariant.objects.create(
            product=cls.inactive_variant_only, name="Blue", sku="C2-B", stock=9, is_active=False
        )

    def names(self, query):
        res = self.client.get(f"/api/products/?{query}")
        self.assertEqual(res.status_code, 200)
        return [p["name"] for p in res.data["results"]]

    def test_in_stock_filter_counts_variant_stock(self):
        names = self.names("in_stock=true&ordering=name")
        self.assertEqual(names, ["Anker Cable", "Case", "JBL Speaker"])
        self.assertEqual(sorted(self.names("in_stock=false")), ["JBL Earbuds", "Old Case"])

    def test_on_sale_filter(self):
        self.assertEqual(sorted(self.names("on_sale=true")), ["Anker Cable", "JBL Speaker"])

    def test_order_by_discount(self):
        # JBL Speaker 50% off, Anker Cable 20% off, others 0%.
        self.assertEqual(self.names("on_sale=true&ordering=-discount_pct"), ["JBL Speaker", "Anker Cable"])

    def test_order_by_best_selling_ignores_cancelled(self):
        user = get_user_model().objects.create_user(username="u", email="u@x.com", password="pass12345")
        ok = Order.objects.create(user=user, subtotal=1, total=1)
        cancelled = Order.objects.create(user=user, subtotal=1, total=1, status="cancelled")
        for order, slug, qty in [(ok, self.anker_deal.slug, 2), (ok, self.jbl_big_deal.slug, 5),
                                 (cancelled, self.anker_deal.slug, 50)]:
            OrderItem.objects.create(order=order, product_name="x", product_slug=slug, price=1, quantity=qty)
        names = self.names("ordering=-sold")
        self.assertEqual(names[:2], ["JBL Speaker", "Anker Cable"])

    def test_filter_options_ignore_brand_and_price_but_respect_other_filters(self):
        res = self.client.get("/api/products/filters/?brand=Anker&price__gte=2500")
        self.assertEqual(res.status_code, 200)
        brands = {b["name"]: b["count"] for b in res.data["brands"]}
        self.assertEqual(brands, {"JBL": 2, "Baseus": 2, "Anker": 1})
        self.assertEqual(res.data["price"], {"min": 150, "max": 3000})

        res = self.client.get("/api/products/filters/?in_stock=true")
        brands = {b["name"]: b["count"] for b in res.data["brands"]}
        self.assertEqual(brands, {"Anker": 1, "JBL": 1, "Baseus": 1})
        self.assertEqual(res.data["price"], {"min": 200, "max": 1000})

        res = self.client.get("/api/products/filters/?search=jbl")
        self.assertEqual({b["name"] for b in res.data["brands"]}, {"JBL"})

    def test_unavailable_products_are_listed_last_for_every_sort(self):
        names = self.names("ordering=price")
        # Cheapest first among available ones; out-of-stock (JBL Earbuds, Old Case) at the end.
        self.assertEqual(names, ["Case", "Anker Cable", "JBL Speaker", "Old Case", "JBL Earbuds"])
        names = self.names("ordering=-price")
        self.assertEqual(names[:3], ["JBL Speaker", "Anker Cable", "Case"])

    def test_slug_route_still_works(self):
        res = self.client.get(f"/api/products/{self.anker_deal.slug}/")
        self.assertEqual(res.status_code, 200)


class ListImageFallbackTests(APITestCase):
    def test_variant_image_used_when_product_has_no_images(self):
        from django.core.files.base import ContentFile

        cat = Category.objects.create(name="Cases")
        product = Product.objects.create(category=cat, name="Phone Case", price=Decimal("300"), sku="PC1", stock=0)
        out = ProductVariant.objects.create(product=product, name="Black", sku="PC1-B", stock=0, sort_order=0)
        out.image.save("black.jpg", ContentFile(b"x"), save=True)
        live = ProductVariant.objects.create(product=product, name="White", sku="PC1-W", stock=3, sort_order=1)
        live.image.save("white.jpg", ContentFile(b"x"), save=True)

        res = self.client.get("/api/products/")
        self.assertEqual(res.status_code, 200)
        image = res.data["results"][0]["primary_image"]
        self.assertIsNotNone(image)
        self.assertIn("white", image["image"])  # in-stock variant preferred

    def test_no_images_anywhere_gives_none(self):
        cat = Category.objects.create(name="Misc")
        Product.objects.create(category=cat, name="Bare", price=Decimal("10"), sku="B1", stock=1)
        res = self.client.get("/api/products/")
        self.assertIsNone(res.data["results"][0]["primary_image"])


class CategoryFilterTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        watches = Category.objects.create(name="Smartwatch")
        cls.watches = watches
        cls.cmf = Category.objects.create(name="CMF", parent=watches)
        Product.objects.create(category=watches, name="CMF Watch Pro", price=1, sku="W1", stock=1, brand="cmf")
        Product.objects.create(category=watches, name="Amazfit Bip", price=1, sku="W2", stock=1, brand="Amazfit")
        Product.objects.create(category=cls.cmf, name="CMF Watch 2", price=1, sku="W3", stock=1)

    def names(self, query):
        res = self.client.get(f"/api/products/?{query}")
        self.assertEqual(res.status_code, 200)
        return sorted(p["name"] for p in res.data["results"])

    def test_parent_category_lists_whole_subtree(self):
        self.assertEqual(
            self.names(f"category={self.watches.id}"),
            ["Amazfit Bip", "CMF Watch 2", "CMF Watch Pro"],
        )

    def test_brand_subcategory_matches_parent_products_by_brand(self):
        self.assertEqual(self.names(f"category={self.cmf.id}"), ["CMF Watch 2", "CMF Watch Pro"])

    def test_category_detail_count_matches_listing(self):
        res = self.client.get(f"/api/categories/{self.cmf.slug}/")
        self.assertEqual(res.data["product_count"], 2)


class StockNotifyTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        from .models import StockNotification

        cls.StockNotification = StockNotification
        cls.category = Category.objects.create(name="Notify")
        cls.sold_out = Product.objects.create(
            category=cls.category, name="Sold Out", price=100, sku="SO-1", stock=0
        )
        cls.available = Product.objects.create(
            category=cls.category, name="Available", price=100, sku="AV-1", stock=4
        )

    def notify(self, product, contact, **extra):
        return self.client.post(
            f"/api/products/{product.slug}/notify/", {"contact": contact, **extra}, format="json"
        )

    def test_phone_and_email_are_accepted_and_deduplicated(self):
        self.assertEqual(self.notify(self.sold_out, "+880 1712-345678").status_code, 201)
        self.assertEqual(self.notify(self.sold_out, "01712345678").status_code, 201)
        self.assertEqual(self.notify(self.sold_out, "Buyer@Example.com").status_code, 201)
        self.assertEqual(self.StockNotification.objects.count(), 2)
        self.assertEqual(self.StockNotification.objects.filter(contact="01712345678").count(), 1)

    def test_rejects_bad_contact_and_in_stock_products(self):
        self.assertEqual(self.notify(self.sold_out, "12345").status_code, 400)
        self.assertEqual(self.notify(self.available, "01712345678").status_code, 400)
        self.assertEqual(self.StockNotification.objects.count(), 0)
