from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from printer_config.models import PrintDocumentType, PrintPaperSize, PrintTemplate
from printer_config.services.sample_templates import default_template_html, sample_template_config


def _cfg_for(*, doc_type: str, paper_size: str) -> dict:
    cfg = sample_template_config()
    cfg["paper_size"] = paper_size

    if paper_size in {PrintPaperSize.POS_58, PrintPaperSize.POS_80}:
        cfg.update(
            {
                "company_info": True,
                "billing_info": False,
                "shipping_info": False,
                "invoice_table": True,
                "bank_details": False,
                "qr_code": True,
                "social_links": False,
                "map_button": False,
                "whatsapp_button": True,
                "signature": False,
                "terms_conditions": False,
            }
        )

    if doc_type == PrintDocumentType.ORDER_SLIP:
        cfg["sections"] = {
            "header": True,
            "items": True,
            "totals": False,
            "assets": True,
            "footer": True,
        }
        cfg["bank_details"] = False
        cfg["terms_conditions"] = False

    if doc_type in {PrintDocumentType.RECEIPT, PrintDocumentType.PAYMENT_RECEIPT}:
        cfg["invoice_table"] = False
        cfg["bank_details"] = False

    return cfg


class Command(BaseCommand):
    help = "Seed professional (Pro) print templates for Invoice / Order Slip / Receipt in both A4 and POS-80."

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Overwrite existing templates with the same slug.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        admin_user = User.objects.filter(is_superuser=True).order_by("id").first()
        overwrite = bool(options.get("overwrite"))

        specs = [
            # (doc_type, label, paper_size, font_size, thermal_layout)
            (PrintDocumentType.INVOICE, "Invoice - Pro (A4)", PrintPaperSize.A4, 12, False),
            (PrintDocumentType.INVOICE, "Invoice - Pro (POS 80mm)", PrintPaperSize.POS_80, 11, True),
            (PrintDocumentType.ORDER_SLIP, "Order Slip - Pro (A4)", PrintPaperSize.A4, 12, False),
            (PrintDocumentType.ORDER_SLIP, "Order Slip - Pro (POS 80mm)", PrintPaperSize.POS_80, 11, True),
            (PrintDocumentType.RECEIPT, "Receipt - Pro (A4)", PrintPaperSize.A4, 12, False),
            (PrintDocumentType.RECEIPT, "Receipt - Pro (POS 80mm)", PrintPaperSize.POS_80, 11, True),
        ]

        created = 0
        updated = 0
        for doc_type, name, paper_size, font_size, thermal_layout in specs:
            slug = slugify(f"{doc_type}-pro-{paper_size}")
            cfg = _cfg_for(doc_type=doc_type, paper_size=paper_size)
            defaults = {
                "name": name,
                "document_type": doc_type,
                "description": f"Professional {doc_type} template ({paper_size}) with QR/links/status badges.",
                "is_active": True,
                "is_admin_approved": True,
                "is_default": False,
                "restrict_basic_plan": False,
                "admin_only": False,
                "paper_size": paper_size,
                "font_size": font_size,
                "thermal_layout": thermal_layout,
                "html_template": default_template_html(doc_type),
                "css_template": "",
                "json_config": cfg,
                "enabled_sections": {},
                "created_by": admin_user,
                "approved_by": admin_user,
            }

            if overwrite:
                obj, was_created = PrintTemplate.objects.update_or_create(slug=slug, defaults=defaults)
                created += 1 if was_created else 0
                updated += 0 if was_created else 1
                self.stdout.write(f"[ok] {obj.slug}")
            else:
                obj, was_created = PrintTemplate.objects.get_or_create(slug=slug, defaults=defaults)
                if was_created:
                    created += 1
                    self.stdout.write(f"[ok] {obj.slug}")
                else:
                    self.stdout.write(f"[skip] {obj.slug}")

        self.stdout.write(self.style.SUCCESS(f"Pro template seeding done. created={created} updated={updated}"))

