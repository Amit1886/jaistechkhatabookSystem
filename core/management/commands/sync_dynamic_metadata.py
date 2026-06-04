from django.core.management.base import BaseCommand

from core.metadata.scanner import scan_models


class Command(BaseCommand):
    help = "Sync scanned Django model metadata into platform_identity DynamicModule/DynamicField tables."

    def handle(self, *args, **options):
        from apps.platform.identity.models import DynamicField, DynamicModule, EnterprisePermission

        module_count = 0
        field_count = 0
        permission_count = 0

        for meta in scan_models():
            module, _ = DynamicModule.objects.update_or_create(
                tenant=None,
                key=meta["key"],
                defaults={
                    "label": meta["label_plural"],
                    "app_label": meta["app_label"],
                    "route_name": meta["api"]["base"],
                    "menu_key": meta["app_label"],
                    "is_active": True,
                    "metadata": {
                        "model_name": meta["model_name"],
                        "db_table": meta["db_table"],
                        "mobile": meta["mobile"],
                        "api": meta["api"],
                    },
                },
            )
            module_count += 1

            for field in meta["fields"]:
                DynamicField.objects.update_or_create(
                    module=module,
                    key=field["name"],
                    defaults={
                        "label": field["label"],
                        "model_path": meta["key"],
                        "field_name": field["name"],
                        "is_sensitive": field["sensitive"],
                        "is_active": True,
                        "metadata": field,
                    },
                )
                field_count += 1

            for action, key in meta["permissions"].items():
                EnterprisePermission.objects.update_or_create(
                    tenant=None,
                    key=key,
                    defaults={
                        "module": module,
                        "label": f"{action.title()} {meta['label']}",
                        "scope": "api",
                        "is_active": True,
                        "metadata": {"action": action, "model": meta["key"]},
                    },
                )
                permission_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {module_count} modules, {field_count} fields, {permission_count} permissions."
            )
        )
