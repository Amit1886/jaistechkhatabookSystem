from __future__ import annotations

import json
import logging
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.utils import timezone

from commerce.models import Product
from .models import (
    BrandKit,
    DesignProject,
    DesignElement,
    DesignFont,
    DesignIcon,
    DesignSticker,
    DesignTemplate,
    DesignVersion,
)

logger = logging.getLogger(__name__)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "content_studio/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recent_projects"] = (
            DesignProject.objects.filter(owner=self.request.user)
            .order_by("-updated_at")[:6]
        )
        context["templates"] = DesignTemplate.objects.filter(is_active=True)[:8]
        context["brand_kits"] = BrandKit.objects.filter(owner=self.request.user)[:3]
        context["project_count"] = DesignProject.objects.filter(owner=self.request.user).count()
        context["published_count"] = DesignProject.objects.filter(
            owner=self.request.user, status="published"
        ).count()
        return context


class DesignProjectListView(LoginRequiredMixin, TemplateView):
    template_name = "content_studio/design_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = DesignProject.objects.filter(owner=self.request.user).order_by("-updated_at")
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        paginator = Paginator(qs, 12)
        context["page_obj"] = paginator.get_page(self.request.GET.get("page"))
        context["status_filter"] = status
        return context


class DesignProjectCreateView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "content_studio/design_form.html")

    def post(self, request):
        title = request.POST.get("title")
        if not title:
            messages.error(request, "Title is required.")
            return redirect("content_studio:design_create")
        project = DesignProject.objects.create(
            title=title,
            owner=request.user,
        )
        messages.success(request, "Design project created successfully.")
        return redirect("content_studio:design_detail", pk=project.pk)


class DesignProjectDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        project = get_object_or_404(DesignProject, pk=pk)
        elements = list(project.elements.values(
            "id", "element_type", "x", "y", "width", "height",
            "rotation", "opacity", "content", "style", "z_index",
        ))
        pages = list(project.pages.values("id", "name", "width", "height", "order"))
        context = {
            "project": project,
            "elements": elements,
            "pages": pages,
            "elements_json": json.dumps(elements),
            "pages_json": json.dumps(pages),
        }
        return render(request, "content_studio/design_detail.html", context)


class DesignProjectEditView(LoginRequiredMixin, View):
    def get(self, request, pk):
        project = get_object_or_404(DesignProject, pk=pk)
        return render(request, "content_studio/design_edit.html", {"project": project})

    def post(self, request, pk):
        project = get_object_or_404(DesignProject, pk=pk)
        project.title = request.POST.get("title", project.title)
        project.status = request.POST.get("status", project.status)
        project.save()
        messages.success(request, "Design project updated successfully.")
        return redirect("content_studio:design_detail", pk=project.pk)


class DesignProjectDuplicateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(DesignProject, pk=pk)
        duplicate = DesignProject.objects.create(
            title=f"{project.title} (Copy)",
            owner=request.user,
            brand_kit=project.brand_kit,
            width=project.width,
            height=project.height,
            background_color=project.background_color,
        )
        messages.success(request, "Design project duplicated successfully.")
        return redirect("content_studio:design_detail", pk=duplicate.pk)


class DesignProjectDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(DesignProject, pk=pk)
        project.delete()
        messages.success(request, "Design project deleted successfully.")
        return redirect("content_studio:design_list")


class DesignProjectRestoreVersionView(LoginRequiredMixin, View):
    def post(self, request, pk, version_id):
        project = get_object_or_404(DesignProject, pk=pk)
        version = get_object_or_404(DesignVersion, pk=version_id, project=project)
        project.metadata = version.snapshot
        project.save()
        messages.success(request, "Design project restored to selected version.")
        return redirect("content_studio:design_detail", pk=project.pk)


class DesignProjectResizeView(LoginRequiredMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(DesignProject, pk=pk)
        width = request.POST.get("width")
        height = request.POST.get("height")
        if width:
            project.width = int(width)
        if height:
            project.height = int(height)
        project.save()
        return JsonResponse({"status": "ok", "width": project.width, "height": project.height})


class DesignProjectPublishView(LoginRequiredMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(DesignProject, pk=pk)
        project.status = "published"
        project.published_at = timezone.now()
        project.save()
        messages.success(request, "Design project published successfully.")
        return redirect("content_studio:design_detail", pk=project.pk)


class DesignProjectExportView(LoginRequiredMixin, View):
    def get(self, request, pk):
        project = get_object_or_404(DesignProject, pk=pk)
        data = {
            "title": project.title,
            "width": project.width,
            "height": project.height,
            "elements": list(project.elements.values()),
        }
        response = JsonResponse(data)
        response["Content-Disposition"] = f'attachment; filename="{project.title}.json"'
        return response


class DesignProjectCreateFromProductView(LoginRequiredMixin, View):
    def get(self, request, pk):
        return render(request, "content_studio/design_from_product.html", {"product_id": pk})

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        project = DesignProject.objects.create(
            title=f"Design for {product.name}",
            owner=request.user,
            width=1080,
            height=1080,
        )
        messages.success(request, "Design project created from product.")
        return redirect("content_studio:design_detail", pk=project.pk)


class DesignTemplateListView(LoginRequiredMixin, TemplateView):
    template_name = "content_studio/template_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = DesignTemplate.objects.filter(is_active=True)
        category = self.request.GET.get("category")
        if category:
            qs = qs.filter(category=category)
        query = self.request.GET.get("q")
        if query:
            qs = qs.filter(title__icontains=query)
        paginator = Paginator(qs, 12)
        context["page_obj"] = paginator.get_page(self.request.GET.get("page"))
        context["categories"] = DesignTemplate.objects.values_list("category", flat=True).distinct()
        context["category_filter"] = category
        context["query"] = query
        return context


class DesignTemplateCreateView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "content_studio/template_form.html")

    def post(self, request):
        title = request.POST.get("title")
        if not title:
            messages.error(request, "Title is required.")
            return redirect("content_studio:template_create")
        template = DesignTemplate.objects.create(
            title=title,
            category=request.POST.get("category", "general"),
        )
        messages.success(request, "Template created successfully.")
        return redirect("content_studio:template_detail", pk=template.pk)


class DesignTemplateDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        template = get_object_or_404(DesignTemplate, pk=pk)
        return render(request, "content_studio/template_detail.html", {"template": template})


class DesignTemplateDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        template = get_object_or_404(DesignTemplate, pk=pk)
        template.delete()
        messages.success(request, "Template deleted successfully.")
        return redirect("content_studio:template_list")


class BrandKitListView(LoginRequiredMixin, TemplateView):
    template_name = "content_studio/brand_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["brand_kits"] = BrandKit.objects.filter(owner=self.request.user)
        return context


class BrandKitCreateView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "content_studio/brand_form.html")

    def post(self, request):
        name = request.POST.get("name")
        if not name:
            messages.error(request, "Name is required.")
            return redirect("content_studio:brand_create")
        brand_kit = BrandKit.objects.create(
            name=name,
            owner=request.user,
            primary_color=request.POST.get("primary_color", "#000000"),
            secondary_color=request.POST.get("secondary_color", "#FFFFFF"),
            font_family=request.POST.get("font_family", "Arial"),
            is_default=not BrandKit.objects.filter(owner=request.user, is_default=True).exists(),
        )
        if request.FILES.get("logo"):
            brand_kit.logo = request.FILES["logo"]
            brand_kit.save()
        messages.success(request, "Brand kit created successfully.")
        return redirect("content_studio:brand_detail", pk=brand_kit.pk)


class BrandKitDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        brand_kit = get_object_or_404(BrandKit, pk=pk)
        return render(request, "content_studio/brand_detail.html", {"brand_kit": brand_kit})


class DesignEditorView(LoginRequiredMixin, View):
    def get(self, request, pk):
        project = get_object_or_404(
            DesignProject.objects.prefetch_related("elements", "pages", "brand_kit"),
            pk=pk,
        )
        scene = {
            "project": {
                "id": project.pk,
                "title": project.title,
                "width": project.width,
                "height": project.height,
                "background_color": project.background_color,
                "status": project.status,
            },
            "elements": list(project.elements.values(
                "id", "element_type", "x", "y", "width", "height",
                "rotation", "opacity", "content", "style", "z_index",
            )),
            "pages": list(project.pages.values("id", "name", "width", "height", "order")),
            "brand_kit": {
                "primary_color": project.brand_kit.primary_color,
                "secondary_color": project.brand_kit.secondary_color,
                "font_family": project.brand_kit.font_family,
            }
            if project.brand_kit
            else None,
        }
        context = {
            "project": project,
            "scene_json": json.dumps(scene),
            "fonts_json": json.dumps(list(DesignFont.objects.filter(is_active=True).values("name", "family"))),
            "icons_json": json.dumps(list(DesignIcon.objects.filter(is_active=True).values("name", "svg_content", "tags"))),
            "stickers_json": json.dumps(list(DesignSticker.objects.filter(is_active=True).values("id", "name", "tags"))),
            "templates_json": json.dumps(
                list(DesignTemplate.objects.filter(is_active=True).values("id", "title", "category", "config"))
            ),
        }
        return render(request, "content_studio/editor.html", context)


class DesignAdvancedEditorView(LoginRequiredMixin, View):
    def get(self, request, pk):
        project = get_object_or_404(DesignProject, pk=pk)
        return render(
            request,
            "content_studio/advanced_editor.html",
            {"project": project, "scene_json": json.dumps({})},
        )


class ThemesView(LoginRequiredMixin, TemplateView):
    template_name = "content_studio/themes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_kits = list(
            BrandKit.objects.filter(owner=self.request.user).values(
                "name", "primary_color", "secondary_color"
            )
        )
        defaults = [
            {"name": "Classic", "primary": "#0F172A", "secondary": "#F1F5F9"},
            {"name": "Vibrant", "primary": "#FF6B6B", "secondary": "#4ECDC4"},
            {"name": "Minimal", "primary": "#000000", "secondary": "#FFFFFF"},
            {"name": "Ocean", "primary": "#0EA5E9", "secondary": "#0F172A"},
        ]
        context["palettes"] = user_kits if user_kits else defaults
        return context


class SocialPublishView(LoginRequiredMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(DesignProject, pk=pk)
        platform = request.POST.get("platform")
        messages.success(request, f"Published to {platform} successfully.")
        return redirect("content_studio:design_detail", pk=project.pk)


class StudioSPAView(LoginRequiredMixin, TemplateView):
    template_name = "content_studio/spa.html"
