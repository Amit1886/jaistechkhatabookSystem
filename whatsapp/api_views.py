from __future__ import annotations

from datetime import timedelta

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count, Q

from whatsapp.models import (
    Bot,
    BotFlow,
    BotMessage,
    BotTemplate,
    BroadcastCampaign,
    Customer,
    WhatsAppAccount,
    WhatsAppSession,
    WhatsAppMessage,
)
from whatsapp.serializers import (
    BotFlowSerializer,
    BotMessageSerializer,
    BotSerializer,
    BotTemplateSerializer,
    BroadcastCampaignSerializer,
    CustomerSerializer,
    WhatsAppAccountSerializer,
    WhatsAppMessageLogSerializer,
)
from whatsapp.tasks import run_broadcast_campaign

from khatapro import DISABLE_CELERY


class IsAuthenticated(permissions.IsAuthenticated):
    pass


class WhatsAppAccountViewSet(viewsets.ModelViewSet):
    serializer_class = WhatsAppAccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = WhatsAppAccount.objects.all().select_related("owner")
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs.order_by("-updated_at", "-created_at")
        return qs.filter(owner=self.request.user).order_by("-updated_at", "-created_at")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def healthcheck(self, request, pk=None):
        account: WhatsAppAccount = self.get_object()
        try:
            from whatsapp.services.provider_clients import healthcheck

            res = healthcheck(account)
            account.status = WhatsAppAccount.Status.CONNECTED if res.ok else WhatsAppAccount.Status.ERROR
            account.touch_seen()
            return Response({"ok": res.ok, "status_code": res.status_code, "provider": res.provider, "response": res.response_text})
        except Exception as e:
            account.status = WhatsAppAccount.Status.ERROR
            account.save(update_fields=["status", "updated_at"])
            return Response({"ok": False, "error": f"{type(e).__name__}: {e}"}, status=400)

    @action(detail=True, methods=["post"])
    def request_qr(self, request, pk=None):
        """
        For WEB_GATEWAY accounts: asks the gateway to generate a QR payload.
        """
        account: WhatsAppAccount = self.get_object()
        if account.provider != WhatsAppAccount.Provider.WEB_GATEWAY:
            return Response({"ok": False, "error": "QR login is supported only for web_gateway accounts"}, status=400)

        try:
            from whatsapp.services.provider_clients import get_outbound_client

            client = get_outbound_client(account)
            res = client.request_qr()  # type: ignore[attr-defined]
        except Exception as e:
            account.status = WhatsAppAccount.Status.ERROR
            account.save(update_fields=["status", "updated_at"])
            return Response({"ok": False, "error": f"{type(e).__name__}: {e}"}, status=400)

        sess = (
            WhatsAppSession.objects.filter(account=account)
            .order_by("-updated_at", "-created_at")
            .first()
        )
        if not sess:
            sess = WhatsAppSession.objects.create(account=account, status=WhatsAppSession.Status.QR_REQUIRED)
        sess.status = WhatsAppSession.Status.QR_REQUIRED if res.ok else WhatsAppSession.Status.ERROR
        sess.qr_payload = res.response_text or ""
        sess.last_qr_at = timezone.now()
        sess.last_error = "" if res.ok else (res.response_text or "")[:2000]
        sess.save(update_fields=["status", "qr_payload", "last_qr_at", "last_error", "updated_at"])

        account.status = WhatsAppAccount.Status.CONNECTING if res.ok else WhatsAppAccount.Status.ERROR
        account.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "ok": res.ok,
                "account_status": account.status,
                "session_id": str(sess.id),
                "session_status": sess.status,
                "qr_payload": sess.qr_payload,
            }
        )

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """
        Basic WhatsApp analytics for a single account.
        Query params:
        - days (default 7)
        """
        account: WhatsAppAccount = self.get_object()
        try:
            days = int(request.query_params.get("days") or 7)
        except Exception:
            days = 7
        days = max(1, min(days, 90))
        since = timezone.now() - timedelta(days=days)

        logs = WhatsAppMessage.objects.filter(whatsapp_account=account, created_at__gte=since)
        inbound = logs.filter(direction=WhatsAppMessage.Direction.INBOUND).count()
        outbound = logs.filter(direction=WhatsAppMessage.Direction.OUTBOUND).count()

        # Orders created via WhatsApp (best-effort) by looking at the order inbox mapping.
        try:
            from commerce.models import WhatsAppOrderInbox

            orders_qs = WhatsAppOrderInbox.objects.filter(whatsapp_account=account, created_at__gte=since).exclude(order__isnull=True)
            orders_count = orders_qs.count()
        except Exception:
            orders_count = 0

        unique_customers = logs.filter(direction=WhatsAppMessage.Direction.INBOUND).values("customer_id").exclude(customer_id__isnull=True).distinct().count()
        processed = logs.filter(status=WhatsAppMessage.Status.PROCESSED).count()
        failed = logs.filter(status=WhatsAppMessage.Status.FAILED).count()

        conversion = 0.0
        if inbound > 0:
            conversion = round((orders_count / float(inbound)) * 100.0, 2)

        # Top intents
        intents = (
            logs.values("parsed_intent")
            .exclude(parsed_intent="")
            .annotate(c=Count("id"))
            .order_by("-c")[:10]
        )

        return Response(
            {
                "ok": True,
                "since": since.isoformat(),
                "days": days,
                "messages_received": inbound,
                "messages_sent": outbound,
                "unique_customers": unique_customers,
                "orders_from_whatsapp": orders_count,
                "conversion_rate_percent": conversion,
                "processed": processed,
                "failed": failed,
                "top_intents": list(intents),
            }
        )


class BotViewSet(viewsets.ModelViewSet):
    serializer_class = BotSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Bot.objects.all().select_related("owner", "whatsapp_account")
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs.order_by("-updated_at", "-created_at")
        return qs.filter(owner=self.request.user).order_by("-updated_at", "-created_at")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class BotMessageViewSet(viewsets.ModelViewSet):
    serializer_class = BotMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = BotMessage.objects.all().select_related("bot", "bot__owner")
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs.order_by("-updated_at", "-created_at")
        return qs.filter(bot__owner=self.request.user).order_by("-updated_at", "-created_at")


class BotFlowViewSet(viewsets.ModelViewSet):
    serializer_class = BotFlowSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = BotFlow.objects.all().select_related("bot", "bot__owner")
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs.order_by("priority", "-updated_at")
        return qs.filter(bot__owner=self.request.user).order_by("priority", "-updated_at")


class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Customer.objects.all().select_related("owner", "whatsapp_account", "party")
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs.order_by("-updated_at", "-created_at")
        return qs.filter(owner=self.request.user).order_by("-updated_at", "-created_at")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class BroadcastCampaignViewSet(viewsets.ModelViewSet):
    serializer_class = BroadcastCampaignSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = BroadcastCampaign.objects.all().select_related("owner", "whatsapp_account")
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs.order_by("-updated_at", "-created_at")
        return qs.filter(owner=self.request.user).order_by("-updated_at", "-created_at")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        camp = self.get_object()
        try:
            if DISABLE_CELERY:
                run_broadcast_campaign.run(str(camp.id))  # type: ignore[attr-defined]
            else:
                run_broadcast_campaign.apply_async(args=(str(camp.id),), retry=False, ignore_result=True)
        except Exception:
            run_broadcast_campaign.run(str(camp.id))  # type: ignore[attr-defined]
        return Response({"ok": True, "status": camp.status}, status=status.HTTP_202_ACCEPTED)


class MessageLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WhatsAppMessageLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = WhatsAppMessage.objects.all().select_related("owner", "whatsapp_account", "customer")
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            qs = qs.filter(owner=self.request.user)
        account_id = (self.request.query_params.get("account") or "").strip()
        if account_id:
            qs = qs.filter(whatsapp_account_id=account_id)
        return qs.order_by("-created_at", "-id")


class BotTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = BotTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = BotTemplate.objects.all().select_related("owner")
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs.order_by("-updated_at", "-created_at")
        return qs.filter(Q(owner__isnull=True, is_active=True) | Q(owner=self.request.user)).order_by("name")

    def perform_create(self, serializer):
        if self.request.user.is_staff or self.request.user.is_superuser:
            serializer.save()
        else:
            serializer.save(owner=self.request.user, is_active=True)

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        if not (request.user.is_staff or request.user.is_superuser) and getattr(obj, "owner_id", None) != request.user.id:
            return Response({"detail": "forbidden"}, status=403)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if not (request.user.is_staff or request.user.is_superuser) and getattr(obj, "owner_id", None) != request.user.id:
            return Response({"detail": "forbidden"}, status=403)
        return super().destroy(request, *args, **kwargs)
