from django.http import FileResponse, HttpResponseNotFound, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from distribution import models, serializers
from distribution.services.sync import build_download_catalog, publish_distribution_sync, resolve_live_config


def download_center(request):
    catalog = build_download_catalog(request, industry_slug=request.GET.get("industry") or "", user=request.user)
    grouped = []
    for industry in catalog["industries"]:
        builds = [b for b in catalog["builds"] if not b["industries"] or industry["slug"] in b["industries"]]
        grouped.append({"industry": industry, "builds": builds})
    return render(request, "distribution/download_center.html", {"catalog": catalog, "grouped": grouped})


@require_GET
def public_build_download(request, slug):
    build = get_object_or_404(models.SoftwareBuild, slug=slug, is_published=True)
    if build.requires_login and not request.user.is_authenticated:
        return JsonResponse({"detail": "Login required"}, status=401)
    if build.external_url:
        return JsonResponse({"download_url": build.external_url})
    if not build.installer_file:
        return HttpResponseNotFound("Build file not uploaded.")
    return FileResponse(build.installer_file.open("rb"), as_attachment=True, filename=build.installer_file.name.rsplit("/", 1)[-1])


class AdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)


class IndustryViewSet(viewsets.ModelViewSet):
    queryset = models.Industry.objects.all()
    serializer_class = serializers.IndustrySerializer
    permission_classes = [AdminOrReadOnly]


class AppPlatformViewSet(viewsets.ModelViewSet):
    queryset = models.AppPlatform.objects.all()
    serializer_class = serializers.AppPlatformSerializer
    permission_classes = [AdminOrReadOnly]


class FeatureRegistryViewSet(viewsets.ModelViewSet):
    queryset = models.FeatureRegistry.objects.prefetch_related("supported_platforms", "industries").all()
    serializer_class = serializers.FeatureRegistrySerializer
    permission_classes = [AdminOrReadOnly]

    def perform_update(self, serializer):
        obj = serializer.save()
        publish_distribution_sync("feature.updated", {"slug": obj.slug, "version": obj.version, "enabled": obj.is_enabled})


class ModuleRegistryViewSet(viewsets.ModelViewSet):
    queryset = models.ModuleRegistry.objects.prefetch_related("supported_platforms", "features", "industries").all()
    serializer_class = serializers.ModuleRegistrySerializer
    permission_classes = [AdminOrReadOnly]

    def perform_update(self, serializer):
        obj = serializer.save()
        publish_distribution_sync("module.updated", {"slug": obj.slug, "version": obj.version, "enabled": obj.is_enabled})


class SoftwareBuildViewSet(viewsets.ModelViewSet):
    queryset = models.SoftwareBuild.objects.prefetch_related("industries", "modules").select_related("platform").all()
    serializer_class = serializers.SoftwareBuildSerializer
    permission_classes = [AdminOrReadOnly]


class RemoteConfigViewSet(viewsets.ModelViewSet):
    queryset = models.RemoteConfig.objects.select_related("industry", "user").all()
    serializer_class = serializers.RemoteConfigSerializer
    permission_classes = [AdminOrReadOnly]

    def perform_update(self, serializer):
        obj = serializer.save(version=(serializer.instance.version or 0) + 1)
        publish_distribution_sync("remote_config.updated", {"key": obj.key, "scope": obj.scope, "version": obj.version})


class DeviceRegistryViewSet(viewsets.ModelViewSet):
    queryset = models.DeviceRegistry.objects.select_related("owner", "industry", "platform").all()
    serializer_class = serializers.DeviceRegistrySerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"], permission_classes=[permissions.AllowAny])
    def heartbeat(self, request):
        device_uid = request.data.get("device_uid") or request.headers.get("X-Device-Uid") or ""
        if not device_uid:
            return Response({"detail": "device_uid is required"}, status=400)
        platform = models.AppPlatform.objects.filter(code=request.data.get("platform") or "").first()
        industry = models.Industry.objects.filter(slug=request.data.get("industry") or "").first()
        device, _ = models.DeviceRegistry.objects.get_or_create(
            device_uid=device_uid,
            defaults={
                "owner": request.user if request.user.is_authenticated else None,
                "industry": industry,
                "platform": platform,
                "device_type": request.data.get("device_type") or models.DeviceRegistry.DeviceType.WEB,
            },
        )
        device.last_seen_at = timezone.now()
        device.app_version = request.data.get("app_version") or device.app_version
        device.industry = industry or device.industry
        device.platform = platform or device.platform
        device.ip_address = request.META.get("REMOTE_ADDR")
        device.save()
        return Response(serializers.DeviceRegistrySerializer(device, context={"request": request}).data)


class DistributionSyncViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["get", "post"])
    def live_config(self, request):
        data = request.data if request.method == "POST" else request.query_params
        payload = resolve_live_config(
            user=request.user,
            industry_slug=data.get("industry") or "",
            device_uid=data.get("device_uid") or request.headers.get("X-Device-Uid") or "",
            platform_code=data.get("platform") or "",
            app_version=data.get("app_version") or "",
            request=request,
        )
        return Response(payload)

    @action(detail=False, methods=["get"])
    def catalog(self, request):
        return Response(build_download_catalog(request, industry_slug=request.query_params.get("industry") or "", user=request.user))

