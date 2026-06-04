from django.urls import include, path
from rest_framework.routers import DefaultRouter

from crm.views import CallLogViewSet, CustomerNoteViewSet, CustomerProfileViewSet, FollowUpViewSet

router = DefaultRouter()
router.register("customers", CustomerProfileViewSet, basename="crm-customers")
router.register("notes", CustomerNoteViewSet, basename="crm-notes")
router.register("calls", CallLogViewSet, basename="crm-calls")
router.register("followups", FollowUpViewSet, basename="crm-followups")

urlpatterns = [path("", include(router.urls))]

