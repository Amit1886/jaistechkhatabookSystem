from rest_framework import serializers
from .models import GSTRegistration, GSTCategory, GSTTransaction


class GSTRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTRegistration
        fields = "__all__"


class GSTCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTCategory
        fields = "__all__"


class GSTTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTTransaction
        fields = "__all__"
