from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.cache import cache

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
from .permissions import IsOwnerOrReadOnly
from .services import (
    duplicate_design_project,
    save_design_version,
    update_project_scene,
)


class BrandKitViewSet(viewsets.ModelViewSet):
    queryset = BrandKit.objects.all()
    serializer_class = BrandKitSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]


class DesignProjectViewSet(viewsets.ModelViewSet):
    queryset = DesignProject.objects.prefetch_related(
        "elements", "pages", "versions"
    ).select_related("owner", "brand_kit")
    serializer_class = DesignProjectSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    @action(detail=True, methods=["post"], url_path="save-design")
    def save_design(self, request, pk=None):
        project = self.get_object()
        data = request.data
        updated = update_project_scene(
            project=project,
            elements=data.get("elements"),
            pages=data.get("pages"),
            metadata=data.get("metadata"),
            width=data.get("width"),
            height=data.get("height"),
            background_color=data.get("background_color"),
        )
        return Response(updated)

    @action(detail=True, methods=["post"], url_path="snapshot")
    def snapshot(self, request, pk=None):
        project = self.get_object()
        note = request.data.get("note", "Manual snapshot")
        version = save_design_version(project=project, note=note, created_by=request.user)
        return Response({"version": version.version_number, "pk": version.pk})

    @action(detail=True, methods=["get"], url_path="render")
    def render(self, request, pk=None):
        project = self.get_object()
        cached = cache.get(f"studio:render:{project.pk}")
        if cached is None:
            from .render_engine import render_project

            cached = render_project(project)
            cache.set(f"studio:render:{project.pk}", cached, 300)
        return Response({"project": project.title, "data": cached})

    @action(detail=True, methods=["post"], url_path="duplicate")
    def duplicate(self, request, pk=None):
        project = self.get_object()
        new_project = duplicate_design_project(project=project, owner=request.user)
        return Response({"id": new_project.pk, "title": new_project.title})


class DesignElementViewSet(viewsets.ModelViewSet):
    queryset = DesignElement.objects.all()
    serializer_class = DesignElementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs


class DesignPageViewSet(viewsets.ModelViewSet):
    queryset = DesignPage.objects.all()
    serializer_class = DesignPageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs


class DesignCommentViewSet(viewsets.ModelViewSet):
    queryset = DesignComment.objects.all()
    serializer_class = DesignCommentSerializer
    permission_classes = [permissions.IsAuthenticated]


class DesignFontViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DesignFont.objects.filter(is_active=True)
    serializer_class = DesignFontSerializer
    permission_classes = [permissions.AllowAny]


class DesignIconViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DesignIcon.objects.filter(is_active=True)
    serializer_class = DesignIconSerializer
    permission_classes = [permissions.AllowAny]


class DesignStickerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DesignSticker.objects.filter(is_active=True)
    serializer_class = DesignStickerSerializer
    permission_classes = [permissions.AllowAny]


class DesignTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DesignTemplate.objects.filter(is_active=True)
    serializer_class = DesignTemplateSerializer
    permission_classes = [permissions.AllowAny]


class DesignVersionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DesignVersion.objects.all()
    serializer_class = DesignVersionSerializer
    permission_classes = [permissions.IsAuthenticated]


class DesignShareLinkViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DesignShareLink.objects.all()
    serializer_class = DesignShareLinkSerializer
    permission_classes = [permissions.AllowAny]


class UsageRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UsageRecord.objects.all()
    serializer_class = UsageRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
