from __future__ import annotations

import logging

from rest_framework import decorators, permissions, response, status, viewsets
from rest_framework.views import APIView

from printer_config.models import (
    PrintDocumentType,
    PrintMode,
    PrintRenderLog,
    PrintTemplate,
    PrinterConfig,
    PrinterTestLog,
    TemplatePlanAccess,
    UserPrintTemplate,
)
from printer_config.serializers import (
    PrintRenderLogSerializer,
    PrintTemplateSerializer,
    PrinterConfigSerializer,
    PrinterTestLogSerializer,
    TemplatePlanAccessSerializer,
    UserPrintTemplateSerializer,
)
from printer_config.services.access_control import allowed_templates_queryset, select_default_template_for_user
from printer_config.services.context_builder import build_document_context, build_dummy_context
from printer_config.services.placeholder_catalog import get_placeholder_catalog
from printer_config.services.printer_engine import render_invoice_template, test_print
from printer_config.services.template_renderer import render_template_payload

logger = logging.getLogger(__name__)


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser))


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        owner = getattr(obj, "user", None)
        return owner == request.user


class PrinterConfigViewSet(viewsets.ModelViewSet):
    serializer_class = PrinterConfigSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = PrinterConfig.objects.select_related("user").all()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs
        return qs.filter(user=self.request.user)

    def perform_create(self, serializer):
        if self.request.user.is_staff or self.request.user.is_superuser:
            serializer.save()
        else:
            serializer.save(user=self.request.user)

    @decorators.action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        printer = self.get_object()
        result = test_print(printer)
        return response.Response({"result": result})

    @decorators.action(detail=True, methods=["post"])
    def render(self, request, pk=None):
        printer = self.get_object()
        incoming = request.data or {}
        payload = incoming.get("payload") if isinstance(incoming.get("payload"), dict) else {}
        merged = dict(payload)
        for key in ("document_type", "template_id", "user_template_id", "print_mode", "source_model", "source_id"):
            if key in incoming and key not in merged:
                merged[key] = incoming[key]
        html = render_invoice_template(printer, merged)
        return response.Response({"html": html})


class PrinterTestLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PrinterTestLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = PrinterTestLog.objects.select_related("printer", "printer__user").all()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs
        return qs.filter(printer__user=self.request.user)


class PrintTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = PrintTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]
    search_fields = ["name", "slug", "document_type"]
    ordering_fields = ["created_at", "updated_at", "name", "document_type"]

    def get_queryset(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return PrintTemplate.objects.select_related("created_by", "approved_by").prefetch_related("plan_access__plan")
        return allowed_templates_queryset(
            self.request.user,
            document_type=self.request.query_params.get("document_type"),
        ).select_related("created_by", "approved_by")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, approved_by=self.request.user)

    def perform_update(self, serializer):
        if serializer.validated_data.get("is_admin_approved"):
            serializer.save(approved_by=self.request.user)
            return
        serializer.save()

    @decorators.action(detail=False, methods=["get"])
    def placeholders(self, request):
        document_type = request.query_params.get("document_type")
        return response.Response(
            {
                "document_type": document_type,
                "placeholders": get_placeholder_catalog(document_type=document_type),
            }
        )

    @decorators.action(detail=False, methods=["get"])
    def sample_render(self, request):
        document_type = request.query_params.get("document_type", PrintDocumentType.INVOICE)
        print_mode = request.query_params.get("print_mode", PrintMode.DESKTOP)
        template_id = request.query_params.get("template_id")
        template_obj = None
        if template_id:
            template_obj = self.get_queryset().filter(pk=template_id).first()

        context = build_dummy_context(document_type=document_type, user=request.user)
        rendered = render_template_payload(
            document_type=document_type,
            context=context,
            template_obj=template_obj,
            user_template=None,
            print_mode=print_mode,
        )
        return response.Response(rendered)

    @decorators.action(detail=True, methods=["post"])
    def preview(self, request, pk=None):
        template_obj = self.get_object()
        user_template = None
        user_template_id = request.data.get("user_template_id")
        if user_template_id:
            user_template = UserPrintTemplate.objects.filter(
                pk=user_template_id,
                user=request.user,
                is_active=True,
            ).first()

        document_type = request.data.get("document_type") or template_obj.document_type
        print_mode = request.data.get("print_mode") or (user_template.print_mode if user_template else PrintMode.DESKTOP)
        payload = request.data.get("payload", {}) or {}
        context = build_document_context(
            document_type=document_type,
            source_model=request.data.get("source_model", ""),
            source_id=request.data.get("source_id"),
            payload=payload,
            user=request.user,
        )
        rendered = render_template_payload(
            document_type=document_type,
            context=context,
            template_obj=template_obj,
            user_template=user_template,
            print_mode=print_mode,
        )
        PrintRenderLog.objects.create(
            user=request.user,
            template=template_obj,
            user_template=user_template,
            source_model=request.data.get("source_model", ""),
            source_id=str(request.data.get("source_id", "")),
            document_type=document_type,
            print_mode=print_mode,
            paper_size=rendered["config"].get("paper_size", template_obj.paper_size),
            status=PrintRenderLog.Status.SUCCESS,
            payload=payload,
            rendered_html=rendered["html"][:20000],
            rendered_css=rendered["css"][:10000],
        )
        return response.Response(rendered)


class TemplatePlanAccessViewSet(viewsets.ModelViewSet):
    queryset = TemplatePlanAccess.objects.select_related("template", "plan").all()
    serializer_class = TemplatePlanAccessSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    search_fields = ["template__name", "plan__name"]
    ordering_fields = ["updated_at", "created_at"]


class UserPrintTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = UserPrintTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    search_fields = ["name", "document_type", "print_mode"]
    ordering_fields = ["updated_at", "created_at", "name"]

    def get_queryset(self):
        qs = UserPrintTemplate.objects.select_related("template", "user").all()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs
        return qs.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @decorators.action(detail=True, methods=["post"])
    def make_default(self, request, pk=None):
        obj = self.get_object()
        UserPrintTemplate.objects.filter(
            user=obj.user,
            document_type=obj.document_type,
            print_mode=obj.print_mode,
        ).exclude(pk=obj.pk).update(is_default=False)
        obj.is_default = True
        obj.save(update_fields=["is_default", "updated_at"])
        return response.Response({"status": "ok", "message": "Default template updated."})

    @decorators.action(detail=True, methods=["post"])
    def preview(self, request, pk=None):
        user_template = self.get_object()
        template_obj = user_template.template
        payload = request.data.get("payload", {}) or {}
        context = build_document_context(
            document_type=user_template.document_type,
            source_model=request.data.get("source_model", ""),
            source_id=request.data.get("source_id"),
            payload=payload,
            user=request.user,
        )
        rendered = render_template_payload(
            document_type=user_template.document_type,
            context=context,
            template_obj=template_obj,
            user_template=user_template,
            print_mode=request.data.get("print_mode", user_template.print_mode),
        )
        return response.Response(rendered)


class PrintRenderLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PrintRenderLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["document_type", "source_model", "source_id", "status"]
    ordering_fields = ["created_at", "document_type", "status"]

    def get_queryset(self):
        qs = PrintRenderLog.objects.select_related("template", "user_template", "user").all()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs
        return qs.filter(user=self.request.user)


class PrintEngineRenderAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        document_type = request.data.get("document_type", PrintDocumentType.INVOICE)
        source_model = request.data.get("source_model", "")
        source_id = request.data.get("source_id")
        payload = request.data.get("payload", {}) or {}
        template_id = request.data.get("template_id")
        user_template_id = request.data.get("user_template_id")

        user_template = None
        template_obj = None

        if user_template_id:
            user_template_qs = UserPrintTemplate.objects.filter(pk=user_template_id, is_active=True)
            if not (request.user.is_staff or request.user.is_superuser):
                user_template_qs = user_template_qs.filter(user=request.user)
            user_template = user_template_qs.first()
            if not user_template:
                return response.Response({"detail": "User template not found."}, status=status.HTTP_404_NOT_FOUND)
            template_obj = user_template.template
            document_type = user_template.document_type

        if template_id and not template_obj:
            template_obj = allowed_templates_queryset(request.user).filter(pk=template_id).first()
            if not template_obj:
                return response.Response({"detail": "Template not allowed/not found."}, status=status.HTTP_404_NOT_FOUND)
            document_type = template_obj.document_type

        if not template_obj and not user_template:
            template_obj = select_default_template_for_user(request.user, document_type=document_type)

        if not template_obj and not user_template:
            return response.Response({"detail": "No template available for this document type."}, status=status.HTTP_400_BAD_REQUEST)

        print_mode = request.data.get("print_mode") or (user_template.print_mode if user_template else PrintMode.DESKTOP)
        context = build_document_context(
            document_type=document_type,
            source_model=source_model,
            source_id=source_id,
            payload=payload,
            user=request.user,
        )

        try:
            rendered = render_template_payload(
                document_type=document_type,
                context=context,
                template_obj=template_obj,
                user_template=user_template,
                print_mode=print_mode,
            )
            PrintRenderLog.objects.create(
                user=request.user,
                template=template_obj,
                user_template=user_template,
                source_model=source_model,
                source_id=str(source_id or ""),
                document_type=document_type,
                print_mode=print_mode,
                paper_size=rendered["config"].get("paper_size", "a4"),
                status=PrintRenderLog.Status.SUCCESS,
                payload=payload,
                rendered_html=rendered["html"][:20000],
                rendered_css=rendered["css"][:10000],
            )
            return response.Response(rendered)
        except Exception as exc:
            logger.exception("Print render failed: %s", exc)
            PrintRenderLog.objects.create(
                user=request.user,
                template=template_obj,
                user_template=user_template,
                source_model=source_model,
                source_id=str(source_id or ""),
                document_type=document_type,
                print_mode=print_mode,
                paper_size="a4",
                status=PrintRenderLog.Status.FAILED,
                error_message=str(exc),
                payload=payload,
            )
            return response.Response({"detail": "Render failed", "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class PrintPlaceholderAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        document_type = request.query_params.get("document_type")
        return response.Response(
            {
                "document_type": document_type,
                "placeholders": get_placeholder_catalog(document_type=document_type),
            }
        )


class PrintSettingsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            from users.models import UserProfileExt

            profile = UserProfileExt.objects.filter(user=request.user).first()
            preferences = profile.printer_preferences if profile else {}
        except Exception:
            preferences = {}

        templates = allowed_templates_queryset(request.user).values("id", "name", "document_type", "paper_size")
        user_templates = UserPrintTemplate.objects.filter(user=request.user, is_active=True).values(
            "id",
            "name",
            "document_type",
            "print_mode",
            "is_default",
        )
        return response.Response(
            {
                "user_preferences": preferences,
                "options": {
                    "document_types": [choice[0] for choice in PrintDocumentType.choices],
                    "print_modes": [choice[0] for choice in PrintMode.choices],
                    "paper_sizes": [choice[0] for choice in PrintTemplate._meta.get_field("paper_size").choices],
                },
                "templates": list(templates),
                "user_templates": list(user_templates),
            }
        )

    def post(self, request):
        try:
            from users.models import UserProfileExt

            profile, _ = UserProfileExt.objects.get_or_create(user=request.user)
            current = dict(profile.printer_preferences or {})
            incoming = request.data.get("printer_preferences", {}) or {}
            current.update(incoming)
            profile.printer_preferences = current
            profile.save(update_fields=["printer_preferences", "updated_at"])
            return response.Response({"status": "ok", "printer_preferences": current})
        except Exception:
            logger.exception("Failed to save printer preferences")
            return response.Response({"status": "error", "message": "Failed to save printer preferences"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PrintSendAPIView(APIView):
    """Lightweight endpoint for receiving print jobs from POS clients.

    This accepts a JSON payload like { items: [...], total: 123.45 }
    and records a PrintRenderLog entry for debugging. It does NOT attempt
    to contact a physical printer. Intended for quick testing from scanner.js.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payload = request.data or {}
        user = request.user
        try:
            # record a debug render log if model available
            PrintRenderLog.objects.create(
                user=user,
                template=None,
                user_template=None,
                source_model="pos.client",
                source_id=str(payload.get("id", "")),
                document_type=PrintDocumentType.INVOICE,
                print_mode=PrintMode.DESKTOP,
                paper_size="receipt",
                status=PrintRenderLog.Status.SUCCESS,
                payload=payload,
                rendered_html=(str(payload)[:20000]),
            )
        except Exception:
            # swallow logging errors but continue
            logger.exception("Failed to create print log")

        return response.Response({"status": "ok", "message": "print job received"})
