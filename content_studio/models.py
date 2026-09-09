from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class BrandKit(models.Model):
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="brand_kits",
    )
    primary_color = models.CharField(max_length=7, default="#000000")
    secondary_color = models.CharField(max_length=7, default="#FFFFFF")
    font_family = models.CharField(max_length=100, default="Arial")
    logo = models.ImageField(upload_to="brand_kits/", blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class DesignProject(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("in_progress", "In Progress"),
        ("review", "Review"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    title = models.CharField(max_length=200)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="design_projects",
    )
    brand_kit = models.ForeignKey(
        BrandKit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    width = models.PositiveIntegerField(default=1080)
    height = models.PositiveIntegerField(default=1080)
    background_color = models.CharField(max_length=7, default="#FFFFFF")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class DesignElement(models.Model):
    ELEMENT_TYPES = [
        ("text", "Text"),
        ("image", "Image"),
        ("shape", "Shape"),
        ("sticker", "Sticker"),
        ("icon", "Icon"),
    ]

    project = models.ForeignKey(
        DesignProject,
        on_delete=models.CASCADE,
        related_name="elements",
    )
    element_type = models.CharField(max_length=20, choices=ELEMENT_TYPES)
    x = models.FloatField(default=0)
    y = models.FloatField(default=0)
    width = models.FloatField(default=100)
    height = models.FloatField(default=100)
    rotation = models.FloatField(default=0)
    opacity = models.FloatField(default=1.0)
    content = models.TextField(blank=True)
    style = models.JSONField(default=dict, blank=True)
    z_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["z_index", "created_at"]

    def __str__(self):
        return f"{self.element_type} - {self.project.title}"


class DesignPage(models.Model):
    project = models.ForeignKey(
        DesignProject,
        on_delete=models.CASCADE,
        related_name="pages",
    )
    name = models.CharField(max_length=100)
    width = models.PositiveIntegerField(default=1080)
    height = models.PositiveIntegerField(default=1080)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.project.title} - {self.name}"


class DesignComment(models.Model):
    project = models.ForeignKey(
        DesignProject,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    content = models.TextField()
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.author} on {self.project}"


class DesignFont(models.Model):
    name = models.CharField(max_length=100, unique=True)
    family = models.CharField(max_length=100)
    file = models.FileField(upload_to="fonts/")
    is_premium = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class DesignIcon(models.Model):
    name = models.CharField(max_length=100)
    svg_content = models.TextField()
    tags = models.JSONField(default=list, blank=True)
    is_premium = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class DesignSticker(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to="stickers/")
    tags = models.JSONField(default=list, blank=True)
    is_premium = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class DesignTemplate(models.Model):
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    thumbnail = models.ImageField(upload_to="templates/")
    preview_image = models.ImageField(upload_to="templates/", blank=True, null=True)
    config = models.JSONField(default=dict)
    is_premium = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class DesignVersion(models.Model):
    project = models.ForeignKey(
        DesignProject,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.CharField(max_length=20)
    snapshot = models.JSONField(default=dict)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("project", "version_number")

    def __str__(self):
        return f"{self.project.title} v{self.version_number}"


class DesignShareLink(models.Model):
    project = models.ForeignKey(
        DesignProject,
        on_delete=models.CASCADE,
        related_name="share_links",
    )
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    can_edit = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Share link for {self.project.title}"


class UsageRecord(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usage_records",
    )
    project = models.ForeignKey(
        DesignProject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.action}"
