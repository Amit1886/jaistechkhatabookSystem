from django.urls import path
from . import views

app_name = "content_studio"

urlpatterns = [
    path("dashboard", views.DashboardView.as_view(), name="dashboard"),
    path("designs/", views.DesignProjectListView.as_view(), name="design_list"),
    path("designs/create/", views.DesignProjectCreateView.as_view(), name="design_create"),
    path("designs/create/from-product/<int:pk>/", views.DesignProjectCreateFromProductView.as_view(), name="design_create_from_product"),
    path("designs/<int:pk>/", views.DesignProjectDetailView.as_view(), name="design_detail"),
    path("designs/<int:pk>/edit/", views.DesignProjectEditView.as_view(), name="design_edit"),
    path("designs/<int:pk>/duplicate/", views.DesignProjectDuplicateView.as_view(), name="design_duplicate"),
    path("designs/<int:pk>/delete/", views.DesignProjectDeleteView.as_view(), name="design_delete"),
    path("designs/<int:pk>/resize/", views.DesignProjectResizeView.as_view(), name="design_resize"),
    path("designs/<int:pk>/publish/", views.DesignProjectPublishView.as_view(), name="design_publish"),
    path("designs/<int:pk>/export/", views.DesignProjectExportView.as_view(), name="design_export"),
    path("designs/<int:pk>/restore-version/", views.DesignProjectRestoreVersionView.as_view(), name="design_restore_version"),
    path("templates/", views.DesignTemplateListView.as_view(), name="template_list"),
    path("templates/create/", views.DesignTemplateCreateView.as_view(), name="template_create"),
    path("templates/<int:pk>/", views.DesignTemplateDetailView.as_view(), name="template_detail"),
    path("templates/<int:pk>/delete/", views.DesignTemplateDeleteView.as_view(), name="template_delete"),
    path("brands/", views.BrandKitListView.as_view(), name="brand_list"),
    path("brands/create/", views.BrandKitCreateView.as_view(), name="brand_create"),
    path("brands/<int:pk>/", views.BrandKitDetailView.as_view(), name="brand_detail"),
    path("designs/<int:pk>/editor/", views.DesignEditorView.as_view(), name="design_editor"),
    path("designs/<int:pk>/advanced-editor/", views.DesignAdvancedEditorView.as_view(), name="design_advanced_editor"),
    path("themes/", views.ThemesView.as_view(), name="themes"),
    path("social/publish/", views.SocialPublishView.as_view(), name="social_publish"),
    path("spa/", views.StudioSPAView.as_view(), name="spa"),
]
