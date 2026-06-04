from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0015_seed_default_plans"),
    ]

    operations = [
        migrations.AddField(
            model_name="featureregistry",
            name="is_advanced",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="featureregistry",
            name="dependencies",
            field=models.ManyToManyField(
                blank=True,
                help_text="If enabled for a user, dependencies are auto-enabled (backend).",
                related_name="dependents",
                to="billing.featureregistry",
            ),
        ),
    ]
