from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import (
    BrandKitViewSet,
    DesignProjectViewSet,
    DesignElementViewSet,
    DesignPageViewSet,
    DesignCommentViewSet,
    DesignFontViewSet,
    DesignIconViewSet,
    DesignStickerViewSet,
    DesignTemplateViewSet,
    DesignVersionViewSet,
    DesignShareLinkViewSet,
    UsageRecordViewSet,
)

router = DefaultRouter()
router.register(r"brand-kits", BrandKitViewSet, basename="brand-kit")
router.register(r"projects", DesignProjectViewSet, basename="project")
router.register(r"elements", DesignElementViewSet, basename="element")
router.register(r"pages", DesignPageViewSet, basename="page")
router.register(r"comments", DesignCommentViewSet, basename="comment")
router.register(r"fonts", DesignFontViewSet, basename="font")
router.register(r"icons", DesignIconViewSet, basename="icon")
router.register(r"stickers", DesignStickerViewSet, basename="sticker")
router.register(r"templates", DesignTemplateViewSet, basename="template")
router.register(r"versions", DesignVersionViewSet, basename="version")
router.register(r"share-links", DesignShareLinkViewSet, basename="share-link")
router.register(r"usage", UsageRecordViewSet, basename="usage")

urlpatterns = [
    path("", include(router.urls)),
]
