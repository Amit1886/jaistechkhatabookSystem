from django.contrib import admin
from .models import (
    BrandKit,
    DesignProject,
    DesignElement,
    DesignPage,
    DesignComment,
    DesignFont,
    DesignIcon,
    DesignSticker,
    DesignTemplate,
    DesignVersion,
    DesignShareLink,
    UsageRecord,
)


@admin.register(BrandKit)
class BrandKitAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "primary_color", "is_default", "created_at")
    search_fields = ("name", "owner__username")
    list_filter = ("is_default",)


@admin.register(DesignProject)
class DesignProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "width", "height", "published_at")
    search_fields = ("title", "owner__username")
    list_filter = ("status",)


@admin.register(DesignElement)
class DesignElementAdmin(admin.ModelAdmin):
    list_display = ("project", "element_type", "x", "y", "z_index")
    search_fields = ("project__title",)
    list_filter = ("element_type",)


@admin.register(DesignPage)
class DesignPageAdmin(admin.ModelAdmin):
    list_display = ("project", "name", "order")
    search_fields = ("project__title", "name")


@admin.register(DesignComment)
class DesignCommentAdmin(admin.ModelAdmin):
    list_display = ("project", "author", "resolved", "created_at")
    search_fields = ("project__title", "author__username")
    list_filter = ("resolved",)


@admin.register(DesignFont)
class DesignFontAdmin(admin.ModelAdmin):
    list_display = ("name", "family", "is_premium")
    search_fields = ("name", "family")


@admin.register(DesignIcon)
class DesignIconAdmin(admin.ModelAdmin):
    list_display = ("name", "is_premium")
    search_fields = ("name",)


@admin.register(DesignSticker)
class DesignStickerAdmin(admin.ModelAdmin):
    list_display = ("name", "is_premium")
    search_fields = ("name",)


@admin.register(DesignTemplate)
class DesignTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_premium", "is_active")
    search_fields = ("title", "category")
    list_filter = ("is_premium", "is_active")


@admin.register(DesignVersion)
class DesignVersionAdmin(admin.ModelAdmin):
    list_display = ("project", "version_number", "created_by", "created_at")
    search_fields = ("project__title", "version_number")


@admin.register(DesignShareLink)
class DesignShareLinkAdmin(admin.ModelAdmin):
    list_display = ("project", "token", "can_edit", "expires_at")
    search_fields = ("project__title", "token")


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "project", "action", "created_at")
    search_fields = ("user__username", "action")
    list_filter = ("action",)
