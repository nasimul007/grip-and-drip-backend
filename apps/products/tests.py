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
