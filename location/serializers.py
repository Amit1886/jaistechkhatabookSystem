from rest_framework import serializers

from .models import Country, District, Pincode, State


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "name", "iso2", "iso3", "phone_code", "is_active"]


class StateSerializer(serializers.ModelSerializer):
    country = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all())
    country_detail = CountrySerializer(source="country", read_only=True)

    class Meta:
        model = State
        fields = ["id", "name", "code", "is_active", "country", "country_detail"]


class DistrictSerializer(serializers.ModelSerializer):
    state = serializers.PrimaryKeyRelatedField(queryset=State.objects.all())
    state_detail = StateSerializer(source="state", read_only=True)

    class Meta:
        model = District
        fields = ["id", "name", "is_active", "state", "state_detail"]


class PincodeSerializer(serializers.ModelSerializer):
    district = serializers.PrimaryKeyRelatedField(queryset=District.objects.all())
    district_detail = DistrictSerializer(source="district", read_only=True)

    class Meta:
        model = Pincode
        fields = [
            "id",
            "code",
            "locality",
            "city",
            "latitude",
            "longitude",
            "is_active",
            "district",
            "district_detail",
        ]
