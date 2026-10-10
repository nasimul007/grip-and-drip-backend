import apps.products.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0003_update_product_upload_to"),
    ]

    operations = [
        migrations.CreateModel(
            name="Brand",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, unique=True)),
                ("logo", models.ImageField(blank=True, upload_to=apps.products.models.brand_logo_upload_to)),
            ],
            options={"ordering": ["name"]},
        ),
    ]
