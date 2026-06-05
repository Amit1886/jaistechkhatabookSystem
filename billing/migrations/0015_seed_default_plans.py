from decimal import Decimal

from django.db import migrations
from django.utils.text import slugify


def seed_default_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    PlanPermissions = apps.get_model("billing", "PlanPermissions")

    def upsert_plan(name, price_monthly, price_yearly, trial_days, description):
        slug = slugify(name)
        plan = Plan.objects.filter(slug=slug).order_by("id").first()
        if plan is None:
            plan = Plan.objects.filter(name=name).order_by("id").first()
        if plan is None:
            plan = Plan()
        plan.name = name
        plan.slug = slug
        plan.active = True
        plan.price = Decimal(str(price_monthly or 0))
        plan.price_monthly = Decimal(str(price_monthly or 0))
        plan.price_yearly = Decimal(str(price_yearly or 0))
        plan.trial_days = int(trial_days or 0)
        plan.description = description
        plan.save()
        PlanPermissions.objects.get_or_create(plan=plan)
        return plan

    # Keep names stable; the landing page maps them to Free/Pro/Pro Max tiers.
    upsert_plan(
        name="Free Plan",
        price_monthly=Decimal("0.00"),
        price_yearly=Decimal("0.00"),
        trial_days=7,
        description="Designed for new users who want to try basic billing with simple limits.",
    )
    upsert_plan(
        name="Basic Plan",
        price_monthly=Decimal("499.00"),
        price_yearly=Decimal("4999.00"),
        trial_days=0,
        description="For growing businesses that need unlimited entries and better controls.",
    )
    upsert_plan(
        name="Premium Plan",
        price_monthly=Decimal("999.00"),
        price_yearly=Decimal("9999.00"),
        trial_days=0,
        description="For advanced workflows, multi-outlet needs, and enterprise-level reporting.",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0014_sync_feature_registry"),
    ]

    operations = [
        migrations.RunPython(seed_default_plans, migrations.RunPython.noop),
    ]

