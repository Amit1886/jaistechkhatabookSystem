from django.db import migrations


def seed_marketplace_apps(apps, schema_editor):
    MarketplaceApp = apps.get_model("vendors", "MarketplaceApp")

    seeds = [
        {
            "code": "shopify_connector",
            "name": "Shopify Connector",
            "category": "sales",
            "short_description": "Connect a Shopify store and sync orders/products.",
            "description": "OAuth connect yourstore.myshopify.com, then sync orders/products into the system.",
            "rating": 4.8,
            "is_active": True,
            "is_builtin": True,
            "default_config": {"sync_orders": True, "sync_products": True},
        },
        {
            "code": "shiprocket_tools",
            "name": "Shiprocket Tools",
            "category": "shipping",
            "short_description": "Shipping labels, tracking and courier workflows (India).",
            "description": "Configure Shiprocket credentials and generate shipments for storefront orders.",
            "rating": 4.6,
            "is_active": True,
            "is_builtin": True,
            "default_config": {},
        },
        {
            "code": "whatsapp_reminders",
            "name": "WhatsApp Reminders",
            "category": "marketing",
            "short_description": "Send WhatsApp messages for abandoned cart and order updates.",
            "description": "Automated WhatsApp campaigns with templates and scheduling.",
            "rating": 4.7,
            "is_active": True,
            "is_builtin": True,
            "default_config": {"enabled": True},
        },
        {
            "code": "sms_notifications",
            "name": "SMS Notifications",
            "category": "marketing",
            "short_description": "Order and payment SMS alerts.",
            "description": "Configure SMS provider credentials and send transactional messages.",
            "rating": 4.4,
            "is_active": True,
            "is_builtin": True,
            "default_config": {"enabled": True},
        },
        {
            "code": "support_chat_widget",
            "name": "Support Chat Widget",
            "category": "support",
            "short_description": "Add a support chat widget to your storefront.",
            "description": "Collect leads and answer FAQs with a lightweight chat widget.",
            "rating": 4.3,
            "is_active": True,
            "is_builtin": True,
            "default_config": {},
        },
    ]

    for s in seeds:
        MarketplaceApp.objects.update_or_create(code=s["code"], defaults=s)


def unseed_marketplace_apps(apps, schema_editor):
    MarketplaceApp = apps.get_model("vendors", "MarketplaceApp")
    MarketplaceApp.objects.filter(
        code__in=[
            "shopify_connector",
            "shiprocket_tools",
            "whatsapp_reminders",
            "sms_notifications",
            "support_chat_widget",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0011_vendorshopifyconnection"),
    ]

    operations = [
        migrations.RunPython(seed_marketplace_apps, reverse_code=unseed_marketplace_apps),
    ]

