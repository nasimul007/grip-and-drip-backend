from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0009_brand_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="gtin",
            field=models.CharField(blank=True, max_length=14, help_text="Barcode (EAN/UPC) if the product has one; improves Google Shopping listings."),
        ),
        migrations.AddField(
            model_name="product",
            name="mpn",
            field=models.CharField(blank=True, max_length=100, help_text="Manufacturer part number, if any."),
        ),
        migrations.CreateModel(
            name="ProductSlugHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_slug", models.SlugField(max_length=255, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="slug_history", to="products.product")),
            ],
        ),
    ]
