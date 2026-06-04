from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from commerce.models import Invoice
from khataapp.models import Party, ReminderLog
from smart_khata.services.credit_score import credit_score_level, update_party_credit_metrics
from smart_khata.services.reminders import send_reminder_for_invoice


class CustomerCreditScoreAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        party_id = (request.query_params.get("party_id") or request.query_params.get("customer_id") or "").strip()
        recalc = (request.query_params.get("recalc") or "").strip().lower() in {"1", "true", "yes", "on"}

        qs = Party.objects.filter(party_type="customer")
        if request.user.is_staff or request.user.is_superuser:
            owner_id = (request.query_params.get("owner_id") or "").strip()
            if owner_id:
                try:
                    qs = qs.filter(owner_id=int(owner_id))
                except Exception:
                    pass
        else:
            qs = qs.filter(owner=request.user)

        if party_id:
            party = get_object_or_404(qs, id=int(party_id))
            if recalc:
                result = update_party_credit_metrics(party)
            else:
                # Use stored fields (fast) while still returning computed level.
                result = update_party_credit_metrics(party)

            return Response(
                {
                    "id": party.id,
                    "name": party.name,
                    "credit_score": int(result.score),
                    "level": result.level,
                    "total_due": str(result.total_due),
                    "average_payment_delay": int(result.average_delay_days),
                    "last_payment_date": result.last_payment_date.isoformat() if result.last_payment_date else None,
                    "components": {
                        "timeliness": int(result.timeliness_score),
                        "frequency": int(result.frequency_score),
                        "outstanding": int(result.outstanding_score),
                    },
                }
            )

        customers = qs.order_by("-credit_score", "name", "id")[:200]
        data = []
        for c in customers:
            score = int(getattr(c, "credit_score", 0) or 0)
            data.append(
                {
                    "id": c.id,
                    "name": c.name,
                    "credit_score": score,
                    "level": credit_score_level(score),
                    "total_due": str(getattr(c, "total_due", 0) or 0),
                    "last_payment_date": c.last_payment_date.isoformat() if getattr(c, "last_payment_date", None) else None,
                }
            )
        return Response({"results": data})


class HighRiskCustomersAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            threshold = int((request.query_params.get("threshold") or "").strip() or 40)
        except Exception:
            threshold = 40

        qs = Party.objects.filter(party_type="customer")
        if request.user.is_staff or request.user.is_superuser:
            owner_id = (request.query_params.get("owner_id") or "").strip()
            if owner_id:
                try:
                    qs = qs.filter(owner_id=int(owner_id))
                except Exception:
                    pass
        else:
            qs = qs.filter(owner=request.user)

        qs = qs.filter(credit_score__lt=threshold).order_by("-total_due", "credit_score", "name", "id")[:200]
        results = [
            {
                "id": c.id,
                "name": c.name,
                "credit_score": int(c.credit_score or 0),
                "level": credit_score_level(int(c.credit_score or 0)),
                "total_due": str(c.total_due or 0),
            }
            for c in qs
        ]
        return Response({"threshold": threshold, "results": results})


class ReminderHistoryAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        party_id = (request.query_params.get("party_id") or "").strip()
        invoice_id = (request.query_params.get("invoice_id") or "").strip()
        channel = (request.query_params.get("channel") or "").strip().lower()
        status_q = (request.query_params.get("status") or "").strip().lower()

        qs = ReminderLog.objects.select_related("party", "invoice").filter(party__party_type="customer")
        if request.user.is_staff or request.user.is_superuser:
            owner_id = (request.query_params.get("owner_id") or "").strip()
            if owner_id:
                try:
                    qs = qs.filter(party__owner_id=int(owner_id))
                except Exception:
                    pass
        else:
            qs = qs.filter(party__owner=request.user)

        if party_id:
            qs = qs.filter(party_id=int(party_id))
        if invoice_id:
            qs = qs.filter(invoice_id=int(invoice_id))
        if channel in {"whatsapp", "sms", "email"}:
            qs = qs.filter(channel=channel)
        if status_q in {"scheduled", "sent", "failed", "skipped"}:
            qs = qs.filter(status=status_q)

        qs = qs.order_by("-created_at", "-id")[:300]

        results = []
        for r in qs:
            results.append(
                {
                    "id": r.id,
                    "party_id": r.party_id,
                    "party_name": getattr(r.party, "name", None),
                    "invoice_id": r.invoice_id,
                    "invoice_number": getattr(r.invoice, "number", None),
                    "reminder_type": r.reminder_type,
                    "tone": getattr(r, "tone", None),
                    "channel": r.channel,
                    "status": r.status,
                    "scheduled_for": r.scheduled_for.isoformat() if r.scheduled_for else None,
                    "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "payload": r.payload or {},
                }
            )

        return Response({"results": results})


class ReminderSendAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        invoice_id = (request.data.get("invoice_id") or "").strip()
        tone = (request.data.get("tone") or "").strip().lower() or None
        channels = request.data.get("channels") or None
        dry_run = str(request.data.get("dry_run") or "").strip().lower() in {"1", "true", "yes", "on"}

        if not invoice_id:
            return Response({"detail": "Missing invoice_id"}, status=status.HTTP_400_BAD_REQUEST)

        invoice = get_object_or_404(
            Invoice.objects.select_related("order", "order__party"),
            id=int(invoice_id),
        )

        # Tenant safety.
        #
        # Some legacy rows can have `order.owner` NULL; fall back to `party.owner` in that case.
        order_owner_id = getattr(invoice.order, "owner_id", None)
        party_owner_id = getattr(getattr(invoice.order, "party", None), "owner_id", None)
        effective_owner_id = order_owner_id or party_owner_id

        is_admin = bool(request.user.is_staff or request.user.is_superuser)
        if not is_admin:
            if not effective_owner_id or effective_owner_id != request.user.id:
                return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        invoice_owner = getattr(invoice.order, "owner", None) or getattr(getattr(invoice.order, "party", None), "owner", None) or request.user

        if channels is not None and not isinstance(channels, list):
            return Response({"detail": "channels must be a list"}, status=status.HTTP_400_BAD_REQUEST)

        res = send_reminder_for_invoice(invoice_owner, invoice, channels=channels, tone=tone, dry_run=dry_run)
        res["timestamp"] = timezone.now().isoformat()
        return Response(res)
