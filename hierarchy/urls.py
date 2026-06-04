from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AgentCustomerAssignmentViewSet

router = DefaultRouter()
router.register("assignments", AgentCustomerAssignmentViewSet, basename="hierarchy-assignments")

urlpatterns = [path("", include(router.urls))]

