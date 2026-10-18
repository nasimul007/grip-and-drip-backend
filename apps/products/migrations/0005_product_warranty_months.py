import re

from django.db import migrations, models


def parse_months(text):
    """'Warranty: 12 Month' / '1 year' / '6 months' -> months, else None."""
    m = re.search(r"warranty[^0-9]{0,12}(\d+)\s*(year|yr|month|mon)", text or "", re.I)
    if not m:
        return None
    n = int(m.group(1))
    return n * 12 if m.group(2).lower().startswith("y") else n


def backfill(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    for product in Product.objects.filter(description__icontains="warranty").only("id", "description"):
        months = parse_months(product.description)
        if months and 0 < months <= 120:
            Product.objects.filter(pk=product.pk).update(warranty_months=months)


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0004_brand"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="warranty_months",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                choices=[(3, "3 months"), (6, "6 months"), (12, "12 months"), (18, "18 months"),
                         (24, "24 months"), (36, "36 months")],
                help_text="Warranty period shown on product cards and the product page. Leave empty for no warranty.",
            ),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
