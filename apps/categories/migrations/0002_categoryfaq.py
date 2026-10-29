from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("categories", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CategoryFAQ",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question", models.CharField(max_length=255)),
                ("answer", models.TextField(help_text="Plain text, 1-3 sentences.")),
                ("sort_order", models.IntegerField(default=0)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="faqs", to="categories.category")),
            ],
            options={"verbose_name": "FAQ", "verbose_name_plural": "FAQs", "ordering": ["sort_order", "pk"]},
        ),
    ]
