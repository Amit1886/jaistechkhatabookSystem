from rest_framework import permissions
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
from .serializers import (
    BrandKitSerializer,
    DesignProjectSerializer,
    DesignElementSerializer,
    DesignPageSerializer,
    DesignCommentSerializer,
    DesignFontSerializer,
    DesignIconSerializer,
    DesignStickerSerializer,
    DesignTemplateSerializer,
    DesignVersionSerializer,
    DesignShareLinkSerializer,
    UsageRecordSerializer,
)


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        owner = getattr(obj, "owner", None)
        return owner == request.user
