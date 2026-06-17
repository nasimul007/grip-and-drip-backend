import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.categories.models import Category
from apps.products.models import Product, ProductImage, ProductVariant, Attribute, AttributeValue

CATEGORY_TREE = {
    "Mobile Covers": {
        "Apple iPhone": ["iPhone 16 Pro Max", "iPhone 16 Pro", "iPhone 16", "iPhone 15 Pro Max", "iPhone 15"],
        "Samsung Galaxy": ["Galaxy S25 Ultra", "Galaxy S25", "Galaxy S24 Ultra", "Galaxy S24"],
        "Google Pixel": ["Pixel 9 Pro", "Pixel 9", "Pixel 8 Pro"],
        "Xiaomi": ["Xiaomi 14", "Redmi Note 13"],
        "OnePlus": ["OnePlus 13", "OnePlus 12"],
    },
    "Wallets": {
        "Minimalist": ["Slim Card Holder", "Magnetic Wallet", "RFID Blocking Wallet"],
        "Premium": ["Leather Bifold", "Metal Wallet", "Smart Tracker Wallet"],
    },
    "Card Holders": {
        "Stick-on": ["Magnetic Stick-on", "Adhesive Card Holder", "PopSocket Card Holder"],
        "Standalone": ["ID Badge Holder", "Business Card Holder", "Travel Card Organizer"],
    },
    "Screen Protectors": {
        "Tempered Glass": ["iPhone Series", "Samsung Series", "Universal Fit"],
    },
    "Charging Accessories": {
        "Cables": ["USB-C Cable", "Lightning Cable", "Multi-Charging Cable"],
        "Adapters": ["Fast Charger", "Wireless Charger", "Car Charger"],
    },
}

PRODUCT_TEMPLATES = {
    "Mobile Covers": [
        {"name": "Ultra Slim Transparent Case", "brand": "Grip & Drip", "price_range": (250, 450), "featured": True},
        {"name": "Shockproof Armor Case", "brand": "Grip & Drip", "price_range": (350, 650), "featured": True},
        {"name": "Leather Wallet Case", "brand": "Grip & Drip", "price_range": (550, 899), "featured": True},
        {"name": "Liquid Silicone Case", "brand": "Grip & Drip", "price_range": (300, 550), "featured": False},
        {"name": "Heavy Duty Rugged Case", "brand": "Grip & Drip", "price_range": (450, 799), "featured": False},
        {"name": "Flip Cover with Stand", "brand": "Grip & Drip", "price_range": (400, 699), "featured": False},
        {"name": "Carbon Fiber Case", "brand": "Grip & Drip", "price_range": (600, 999), "featured": True},
        {"name": "Glitter Sparkle Case", "brand": "Grip & Drip", "price_range": (280, 499), "featured": False},
    ],
    "Wallets": [
        {"name": "Slim Minimalist Wallet", "brand": "Grip & Drip", "price_range": (400, 700), "featured": True},
        {"name": "RFID Blocking Wallet", "brand": "Grip & Drip", "price_range": (500, 899), "featured": True},
        {"name": "Magnetic Money Clip", "brand": "Grip & Drip", "price_range": (350, 599), "featured": False},
        {"name": "Premium Leather Bifold", "brand": "Grip & Drip", "price_range": (800, 1500), "featured": True},
        {"name": "Travel Wallet with Zipper", "brand": "Grip & Drip", "price_range": (600, 1100), "featured": False},
    ],
    "Card Holders": [
        {"name": "Magnetic Phone Card Holder", "brand": "Grip & Drip", "price_range": (200, 399), "featured": True},
        {"name": "PopSocket Card Holder", "brand": "Grip & Drip", "price_range": (250, 450), "featured": False},
        {"name": "Thin Stick-on Card Pocket", "brand": "Grip & Drip", "price_range": (150, 299), "featured": False},
        {"name": "ID Badge Holder with Strap", "brand": "Grip & Drip", "price_range": (180, 350), "featured": False},
        {"name": "Multi-card Travel Organizer", "brand": "Grip & Drip", "price_range": (350, 650), "featured": True},
    ],
    "Screen Protectors": [
        {"name": "Tempered Glass 9H", "brand": "Grip & Drip", "price_range": (150, 350), "featured": True},
        {"name": "Privacy Screen Protector", "brand": "Grip & Drip", "price_range": (300, 550), "featured": False},
        {"name": "Anti Blue Light Glass", "brand": "Grip & Drip", "price_range": (250, 450), "featured": False},
    ],
    "Charging Accessories": [
        {"name": "Fast USB-C Braided Cable", "brand": "Grip & Drip", "price_range": (200, 400), "featured": True},
        {"name": "20W PD Fast Charger", "brand": "Grip & Drip", "price_range": (350, 599), "featured": True},
        {"name": "15W Wireless Charging Pad", "brand": "Grip & Drip", "price_range": (400, 699), "featured": False},
        {"name": "3-in-1 Multi Charging Cable", "brand": "Grip & Drip", "price_range": (250, 450), "featured": False},
        {"name": "Car Charger Adapter", "brand": "Grip & Drip", "price_range": (300, 500), "featured": False},
    ],
}

COLORS = ["Black", "White", "Navy Blue", "Red", "Pink", "Green", "Midnight Green", "Purple", "Clear", "Smoke"]

MATERIALS = ["Silicone", "TPU", "Leather", "Polycarbonate", "Metal", "Fabric"]


class Command(BaseCommand):
    help = "Generates sample categories, products, and variants for development/testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before generating",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self._clear_data()

        self._create_attributes()
        self._create_categories()
        self._create_products()
        self.stdout.write(self.style.SUCCESS("Sample data generated successfully!"))

    def _clear_data(self):
        self.stdout.write("Clearing existing data...")
        ProductImage.objects.all().delete()
        ProductVariant.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        AttributeValue.objects.all().delete()
        Attribute.objects.all().delete()
        self.stdout.write(self.style.WARNING("All data cleared."))

    def _create_attributes(self):
        color_attr, _ = Attribute.objects.get_or_create(name="Color", slug="color")
        material_attr, _ = Attribute.objects.get_or_create(name="Material", slug="material")
        for color in COLORS:
            AttributeValue.objects.get_or_create(attribute=color_attr, value=color, slug=color.lower().replace(" ", "-"))
        for material in MATERIALS:
            AttributeValue.objects.get_or_create(attribute=material_attr, value=material, slug=material.lower())
        self.stdout.write(f"  Created {Attribute.objects.count()} attributes with {AttributeValue.objects.count()} values")

    def _create_categories(self):
        for parent_name, children in CATEGORY_TREE.items():
            parent, created = Category.objects.get_or_create(
                name=parent_name,
                defaults={"description": f"Shop our collection of {parent_name.lower()} at Grip & Drip."},
            )
            if created:
                self.stdout.write(f"    Created category: {parent_name}")
            for child_name, grandchildren in children.items():
                child, created = Category.objects.get_or_create(
                    name=child_name,
                    parent=parent,
                    defaults={"description": f"Browse {child_name} - premium quality at Grip & Drip."},
                )
                if created:
                    self.stdout.write(f"      Created subcategory: {child_name}")
                for grandchild_name in grandchildren:
                    grandchild, created = Category.objects.get_or_create(
                        name=grandchild_name,
                        parent=child,
                        defaults={"description": f"Shop {grandchild_name} cases and accessories."},
                    )
                    if created:
                        self.stdout.write(f"        Created sub-subcategory: {grandchild_name}")
        self.stdout.write(f"  Total categories: {Category.objects.count()}")

    def _create_products(self):
        leaf_categories = Category.objects.filter(children__isnull=True, is_active=True)
        self.stdout.write(f"  Found {leaf_categories.count()} leaf categories for product placement")
        product_count = 0

        for category in leaf_categories:
            top_parent = self._get_top_parent(category)
            templates = PRODUCT_TEMPLATES.get(top_parent, [])
            if not templates:
                continue

            for template in templates:
                price = random.randint(*template["price_range"])
                compare_price = price + random.randint(50, 300) if random.random() > 0.5 else None
                stock = random.choice([0, 5, 10, 15, 25, 50, 100])
                color_choice = random.choice(COLORS)

                product, created = Product.objects.get_or_create(
                    name=f"{template['name']} for {category.name}",
                    category=category,
                    defaults={
                        "description": self._generate_description(template["name"], category.name, template["brand"]),
                        "price": price,
                        "compare_price": compare_price,
                        "sku": f"GD-{category.pk}-{product_count + 1:04d}",
                        "stock": stock,
                        "is_active": True,
                        "is_featured": template["featured"],
                        "brand": template["brand"],
                        "attributes": {"color": color_choice, "material": random.choice(MATERIALS)},
                        "meta_title": f"Buy {template['name']} for {category.name} | Grip & Drip",
                        "meta_description": f"Shop {template['name']} for {category.name} at Grip & Drip. Premium quality with fast shipping across Bangladesh.",
                    },
                )
                if created:
                    self._create_variants(product, color_choice)
                    product_count += 1

        self.stdout.write(f"  Created {product_count} products")

    def _get_top_parent(self, category):
        ancestors = category.get_ancestors(include_self=False)
        if ancestors:
            return ancestors[0].name
        return category.name

    def _generate_description(self, product_name, model_name, brand):
        features = [
            "Premium quality material for long-lasting durability",
            "Precision cutouts for easy access to all ports and buttons",
            "Slim and lightweight design that fits comfortably in your pocket",
            "Raised edges to protect camera and screen from scratches",
            "Supports wireless charging without removal",
        ]
        selected = random.sample(features, 3)
        desc = f"<h3>{product_name} for {model_name}</h3><p>Protect your {model_name} with the {product_name} from {brand}. Designed to provide maximum protection while maintaining a sleek profile.</p><ul>"
        for feature in selected:
            desc += f"<li>{feature}</li>"
        desc += f"</ul><p>Order now and get free delivery within Dhaka metro area. {brand} products come with a 30-day satisfaction guarantee.</p>"
        return desc

    def _create_variants(self, product, base_color):
        variant_names = [f"{base_color}", f"{base_color} + Tempered Glass Bundle"]
        for i, vname in enumerate(variant_names):
            override = product.price + random.choice([0, 50, 100]) if i > 0 else None
            ProductVariant.objects.get_or_create(
                product=product,
                sku=f"{product.sku}-V{i}",
                defaults={
                    "name": vname,
                    "price_override": override,
                    "stock": random.randint(0, 20),
                    "is_active": True,
                    "attributes": {"color": base_color} if i == 0 else {"color": base_color, "bundle": "glass"},
                },
            )
