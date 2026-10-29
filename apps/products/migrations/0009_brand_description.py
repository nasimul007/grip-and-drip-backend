from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0008_product_video_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="brand",
            name="description",
            field=models.TextField(
                blank=True,
                help_text="Short intro shown on the brand page (/brand/<name>); unique text helps search rankings.",
            ),
        ),
    ]
