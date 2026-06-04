from django.urls import include, path
from rest_framework.routers import DefaultRouter

from whatsapp.api_views import (
    BotFlowViewSet,
    BotMessageViewSet,
    BotViewSet,
    BotTemplateViewSet,
    BroadcastCampaignViewSet,
    CustomerViewSet,
    MessageLogViewSet,
    WhatsAppAccountViewSet,
)

router = DefaultRouter()
router.register("accounts", WhatsAppAccountViewSet, basename="wa-account")
router.register("bots", BotViewSet, basename="wa-bot")
router.register("bot-flows", BotFlowViewSet, basename="wa-bot-flow")
router.register("bot-messages", BotMessageViewSet, basename="wa-bot-message")
router.register("customers", CustomerViewSet, basename="wa-customer")
router.register("bot-templates", BotTemplateViewSet, basename="wa-bot-template")
router.register("broadcasts", BroadcastCampaignViewSet, basename="wa-broadcast")
router.register("message-logs", MessageLogViewSet, basename="wa-message-log")

urlpatterns = [path("", include(router.urls))]
