from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from printer_config.models import PrintPaperSize, PrintTemplate
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

    if doc_type == "order_slip":
        cfg["sections"] = {
            "header": True,
            "items": True,
            "totals": False,
            "assets": True,
            "footer": True,
        }
        cfg["bank_details"] = False
        cfg["terms_conditions"] = False

    if doc_type in {"receipt", "payment_receipt"}:
        cfg["invoice_table"] = False
        cfg["bank_details"] = False

    return cfg


class Command(BaseCommand):
    help = "Migrate PrintTemplate id=1 to the latest Pro HTML/JSON (keeps same record id for admin page)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--set-default",
            action="store_true",
            help="Also make template #1 default for its document_type (and unset other defaults).",
        )

    def handle(self, *args, **options):
        obj = PrintTemplate.objects.filter(pk=1).first()
        if not obj:
            raise CommandError("PrintTemplate id=1 not found.")

        doc_type = (obj.document_type or "").strip().lower()
        paper_size = obj.paper_size or PrintPaperSize.A4

        if not doc_type:
            raise CommandError("PrintTemplate id=1 has empty document_type.")

        cfg = _cfg_for(doc_type=doc_type, paper_size=paper_size)

        is_pos = paper_size in {PrintPaperSize.POS_58, PrintPaperSize.POS_80}
        obj.html_template = default_template_html(doc_type)
        obj.css_template = ""
        obj.json_config = cfg
        obj.enabled_sections = cfg.get("sections", {}) or {}
        obj.font_size = 11 if is_pos else 12
        obj.thermal_layout = bool(is_pos)
        obj.is_active = True
        obj.is_admin_approved = True

        obj.save(
            update_fields=[
                "html_template",
                "css_template",
                "json_config",
                "enabled_sections",
                "font_size",
                "thermal_layout",
                "is_active",
                "is_admin_approved",
                "updated_at",
            ]
        )

        if options.get("set_default"):
            PrintTemplate.objects.filter(document_type=obj.document_type).exclude(pk=obj.pk).update(is_default=False)
            obj.is_default = True
            obj.save(update_fields=["is_default", "updated_at"])

        self.stdout.write(self.style.SUCCESS(f"[ok] migrated PrintTemplate id=1 ({obj.slug}) to Pro ({paper_size})"))

