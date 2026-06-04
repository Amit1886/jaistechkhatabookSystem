from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from printer_config.models import PrintDocumentType, PrintPaperSize, PrintTemplate
from printer_config.services.sample_templates import default_template_html, sample_template_config


class Command(BaseCommand):
    help = "Seed default dynamic print templates for all supported document types."

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

        created = 0
        updated = 0
        for doc_type, label in PrintDocumentType.choices:
            name = f"{label} - Default"
            slug = slugify(f"{doc_type}-default")
            cfg = sample_template_config()
            defaults = {
                "name": name,
                "document_type": doc_type,
                "description": f"System default template for {label}",
                "is_active": True,
                "is_admin_approved": True,
                "is_default": True,
                "restrict_basic_plan": False,
                "admin_only": False,
                "paper_size": PrintPaperSize.A4,
                "html_template": default_template_html(doc_type),
                # BASE_TEMPLATE_CSS is always injected by renderer; keep this as "custom overrides only".
                "css_template": "",
                "json_config": cfg,
                "enabled_sections": cfg.get("sections", {}),
                "created_by": admin_user,
                "approved_by": admin_user,
            }

            if overwrite:
                obj, was_created = PrintTemplate.objects.update_or_create(slug=slug, defaults=defaults)
                if was_created:
                    created += 1
                else:
                    updated += 1
                self.stdout.write(f"[ok] {obj.slug}")
            else:
                obj, was_created = PrintTemplate.objects.get_or_create(slug=slug, defaults=defaults)
                if was_created:
                    created += 1
                    self.stdout.write(f"[ok] {obj.slug}")
                else:
                    self.stdout.write(f"[skip] {obj.slug}")

        self.stdout.write(
            self.style.SUCCESS(f"Template seeding done. created={created} updated={updated}")
        )
