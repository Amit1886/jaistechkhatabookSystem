from __future__ import annotations

from django.core.management.base import BaseCommand

from whatsapp.models import Bot, BotTemplate


DEFAULT_TEMPLATES = [
    {
        "name": "Welcome Bot",
        "kind": Bot.Kind.WELCOME,
        "description": "Simple welcome + menu message.",
        "payload": {
            "messages": [
                {
                    "key": "welcome",
                    "message_type": "text",
                    "text": "Hi! Welcome.\nType 'help' to see menu.\nType 'products' to browse and order.",
                }
            ],
            "flows": [
                {
                    "name": "Welcome (hi/hello)",
                    "trigger_type": "keyword",
                    "trigger_value": "hi",
                    "actions": [{"type": "send_message_key", "key": "welcome"}],
                    "priority": 10,
                    "is_active": True,
                },
                {
                    "name": "Welcome (start/menu)",
                    "trigger_type": "keyword",
                    "trigger_value": "start",
                    "actions": [{"type": "send_message_key", "key": "welcome"}],
                    "priority": 11,
                    "is_active": True,
                },
            ],
        },
    },
    {
        "name": "Order Bot",
        "kind": Bot.Kind.ORDER,
        "description": "Commerce ordering bot (menu + cart + checkout).",
        "payload": {
            "flows": [
                {
                    "name": "Order (keyword)",
                    "trigger_type": "keyword",
                    "trigger_value": "order",
                    "actions": [{"type": "run_order_bot"}],
                    "priority": 20,
                    "is_active": True,
                }
            ]
        },
    },
    {
        "name": "Payment Bot",
        "kind": Bot.Kind.PAYMENT,
        "description": "Payment guidance + invoice sharing.",
        "payload": {
            "messages": [
                {
                    "key": "payment_help",
                    "message_type": "text",
                    "text": "To pay: add items, type 'checkout', and choose UPI/Card/Netbanking. You'll receive a payment link + invoice PDF.",
                }
            ],
            "flows": [
                {
                    "name": "Payment Help",
                    "trigger_type": "keyword",
                    "trigger_value": "pay",
                    "actions": [{"type": "send_message_key", "key": "payment_help"}],
                    "priority": 30,
                    "is_active": True,
                }
            ],
        },
    },
    {
        "name": "Support Bot",
        "kind": Bot.Kind.SUPPORT,
        "description": "Human handoff template.",
        "payload": {
            "flows": [
                {
                    "name": "Support (keyword)",
                    "trigger_type": "keyword",
                    "trigger_value": "support",
                    "actions": [{"type": "connect_human"}],
                    "priority": 10,
                    "is_active": True,
                }
            ]
        },
    },
    {
        "name": "Lead Generation Bot",
        "kind": Bot.Kind.LEAD,
        "description": "Collect leads/enquiries.",
        "payload": {
            "messages": [
                {
                    "key": "lead_capture",
                    "message_type": "text",
                    "text": "Thanks for your interest. Please share your name + requirement. Our team will contact you shortly.",
                }
            ],
            "flows": [
                {
                    "name": "Lead (keyword)",
                    "trigger_type": "keyword",
                    "trigger_value": "enquiry",
                    "actions": [{"type": "send_message_key", "key": "lead_capture"}],
                    "priority": 15,
                    "is_active": True,
                }
            ],
        },
    },
    {
        "name": "Appointment Booking Bot",
        "kind": Bot.Kind.APPOINTMENT,
        "description": "Basic appointment capture.",
        "payload": {
            "messages": [
                {
                    "key": "appointment",
                    "message_type": "text",
                    "text": "Please share preferred date/time + purpose. We'll confirm your appointment shortly.",
                }
            ],
            "flows": [
                {
                    "name": "Appointment (keyword)",
                    "trigger_type": "keyword",
                    "trigger_value": "appointment",
                    "actions": [{"type": "send_message_key", "key": "appointment"}],
                    "priority": 15,
                    "is_active": True,
                }
            ],
        },
    },
    {
        "name": "Survey Bot",
        "kind": Bot.Kind.SURVEY,
        "description": "Basic post-purchase survey.",
        "payload": {
            "messages": [
                {
                    "key": "survey",
                    "message_type": "text",
                    "text": "Rate your experience (1-5) and share feedback. Thank you!",
                }
            ],
            "flows": [
                {
                    "name": "Survey (keyword)",
                    "trigger_type": "keyword",
                    "trigger_value": "survey",
                    "actions": [{"type": "send_message_key", "key": "survey"}],
                    "priority": 15,
                    "is_active": True,
                }
            ],
        },
    },
]


class Command(BaseCommand):
    help = "Seed default WhatsApp bot templates (admin global library)."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for tpl in DEFAULT_TEMPLATES:
            obj, was_created = BotTemplate.objects.update_or_create(
                owner=None,
                name=tpl["name"],
                defaults={
                    "kind": tpl["kind"],
                    "description": tpl.get("description", ""),
                    "payload": tpl.get("payload", {}),
                    "is_active": True,
                },
            )
            created += 1 if was_created else 0
            updated += 0 if was_created else 1

        self.stdout.write(self.style.SUCCESS(f"WhatsApp templates ready. created={created} updated={updated}"))
