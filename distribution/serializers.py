from rest_framework import serializers

from distribution import models


class IndustrySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Industry
        fields = "__all__"


class AppPlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AppPlatform
        fields = "__all__"


class FeatureRegistrySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.FeatureRegistry
        fields = "__all__"


class ModuleRegistrySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ModuleRegistry
        fields = "__all__"


class IndustryModuleMapSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.IndustryModuleMap
        fields = "__all__"


class SoftwareBuildSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SoftwareBuild
        fields = "__all__"


class DownloadPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DownloadPermission
        fields = "__all__"


class AppVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AppVersion
        fields = "__all__"


class RemoteConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RemoteConfig
        fields = "__all__"


class DeviceRegistrySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DeviceRegistry
        fields = "__all__"


class AppInstallationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AppInstallation
        fields = "__all__"

