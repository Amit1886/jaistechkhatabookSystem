from rest_framework import serializers

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


class BrandKitSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = BrandKit
        fields = [
            "id",
            "name",
            "owner",
            "primary_color",
            "secondary_color",
            "font_family",
            "logo",
            "is_default",
            "created_at",
            "updated_at",
        ]


class DesignElementSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="element_type", read_only=True)

    class Meta:
        model = DesignElement
        fields = [
            "id",
            "project",
            "element_type",
            "type",
            "x",
            "y",
            "width",
            "height",
            "rotation",
            "opacity",
            "content",
            "style",
            "z_index",
            "created_at",
        ]


class DesignPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DesignPage
        fields = ["id", "project", "name", "width", "height", "order", "created_at"]


class DesignCommentSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = DesignComment
        fields = ["id", "project", "author", "content", "resolved", "created_at"]


class DesignFontSerializer(serializers.ModelSerializer):
    class Meta:
        model = DesignFont
        fields = ["id", "name", "family", "is_premium", "is_active", "created_at"]


class DesignIconSerializer(serializers.ModelSerializer):
    class Meta:
        model = DesignIcon
        fields = ["id", "name", "svg_content", "tags", "is_premium", "is_active", "created_at"]


class DesignStickerSerializer(serializers.ModelSerializer):
    class Meta:
        model = DesignSticker
        fields = ["id", "name", "tags", "is_premium", "is_active", "created_at"]


class DesignTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DesignTemplate
        fields = [
            "id",
            "title",
            "category",
            "thumbnail",
            "preview_image",
            "config",
            "is_premium",
            "is_active",
            "created_at",
        ]


class DesignVersionSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = DesignVersion
        fields = ["id", "project", "version_number", "snapshot", "note", "created_by", "created_at"]


class DesignShareLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DesignShareLink
        fields = ["id", "project", "token", "expires_at", "can_edit", "created_at"]


class UsageRecordSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = UsageRecord
        fields = ["id", "user", "project", "action", "metadata", "created_at"]


class DesignProjectSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField(read_only=True)
    brand_kit = BrandKitSerializer(read_only=True)
    elements = DesignElementSerializer(many=True, read_only=True)
    pages = DesignPageSerializer(many=True, read_only=True)
    versions = DesignVersionSerializer(many=True, read_only=True)
    share_links = DesignShareLinkSerializer(many=True, read_only=True)

    class Meta:
        model = DesignProject
        fields = [
            "id",
            "title",
            "owner",
            "brand_kit",
            "status",
            "width",
            "height",
            "background_color",
            "metadata",
            "elements",
            "pages",
            "versions",
            "share_links",
            "published_at",
            "created_at",
            "updated_at",
        ]
