from django.core.management.base import BaseCommand
from content_studio.models import BrandKit, DesignTemplate


class Command(BaseCommand):
    help = "Seed content studio data"

    def handle(self, *args, **options):
        if not BrandKit.objects.exists():
            BrandKit.objects.create(
                name="Default Brand Kit",
                primary_color="#FF6B6B",
                secondary_color="#4ECDC4",
                font_family="Inter",
                is_default=True,
            )
            self.stdout.write(self.style.SUCCESS("Seeded BrandKit"))
        else:
            self.stdout.write("BrandKit already exists")

        if not DesignTemplate.objects.exists():
            DesignTemplate.objects.create(
                title="Social Post",
                category="social",
                config={},
            )
            self.stdout.write(self.style.SUCCESS("Seeded DesignTemplate"))
        else:
            self.stdout.write("DesignTemplate already exists")
