from rest_framework import viewsets, permissions
from .models import GSTRegistration, GSTCategory, GSTTransaction
from .serializers import (
    GSTRegistrationSerializer,
    GSTCategorySerializer,
    GSTTransactionSerializer,
)


class GSTRegistrationViewSet(viewsets.ModelViewSet):
    queryset = GSTRegistration.objects.all()
    serializer_class = GSTRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated]


class GSTCategoryViewSet(viewsets.ModelViewSet):
    queryset = GSTCategory.objects.all()
    serializer_class = GSTCategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class GSTTransactionViewSet(viewsets.ModelViewSet):
    queryset = GSTTransaction.objects.all()
    serializer_class = GSTTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
