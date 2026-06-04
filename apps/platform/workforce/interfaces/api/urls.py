from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.platform.workforce.interfaces.api import views

router = DefaultRouter()
router.register("departments", views.DepartmentViewSet)
router.register("designations", views.DesignationViewSet)
router.register("teams", views.TeamViewSet)
router.register("employees", views.EmployeeProfileViewSet)
router.register("shifts", views.ShiftViewSet)
router.register("shift-assignments", views.ShiftAssignmentViewSet)
router.register("attendance", views.AttendanceLogViewSet)
router.register("leave-requests", views.LeaveRequestViewSet)
router.register("tasks", views.StaffTaskViewSet)
router.register("kpis", views.StaffKPIViewSet)
router.register("devices", views.EmployeeDeviceViewSet)
router.register("sessions", views.EmployeeSessionViewSet)
router.register("documents", views.EmployeeDocumentViewSet)
router.register("activity-logs", views.EmployeeActivityLogViewSet)
router.register("announcements", views.AnnouncementViewSet)
router.register("discussions", views.StaffDiscussionViewSet)
router.register("productivity-signals", views.ProductivitySignalViewSet)
router.register("score-snapshots", views.EmployeeScoreSnapshotViewSet)
router.register("payroll-policies", views.PayrollPolicyViewSet)
router.register("payroll-profiles", views.EmployeePayrollProfileViewSet)
router.register("payroll-runs", views.PayrollRunViewSet)
router.register("payslips", views.PayslipViewSet)
router.register("payouts", views.PayoutInstructionViewSet)
router.register("discipline-cases", views.DisciplineCaseViewSet)
router.register("fraud-risks", views.FraudRiskSignalViewSet)
router.register("hr-insights", views.HRInsightViewSet)
router.register("profitability", views.WorkforceProfitabilitySnapshotViewSet)
router.register("remote-sessions", views.RemoteWorkSessionViewSet)
router.register("remote-activity", views.RemoteActivityEventViewSet)
router.register("gig-tasks", views.GigTaskViewSet)
router.register("marketplace-listings", views.MarketplaceListingViewSet)
router.register("marketplace-applications", views.MarketplaceApplicationViewSet)
router.register("partners", views.PartnerProfileViewSet)
router.register("partner-settlements", views.PartnerSettlementViewSet)
router.register("training-courses", views.TrainingCourseViewSet)
router.register("certifications", views.CertificationViewSet)
router.register("wallets", views.EmployeeWalletViewSet)
router.register("wallet-transactions", views.WalletTransactionViewSet)
router.register("business-network", views.BusinessNetworkNodeViewSet)
router.register("cognitive-profiles", views.CognitiveEmployeeProfileViewSet)
router.register("behavioral-signals", views.BehavioralSignalViewSet)
router.register("transparency-records", views.EmployeeTransparencyRecordViewSet)
router.register("culture-programs", views.CultureEngagementProgramViewSet)
router.register("recognitions", views.EmployeeRecognitionViewSet)
router.register("career-growth-plans", views.CareerGrowthPlanViewSet)
router.register("hr-compliance-ledger", views.HRComplianceLedgerViewSet)
router.register("org-graph-nodes", views.OrganizationalGraphNodeViewSet)
router.register("org-graph-edges", views.OrganizationalGraphEdgeViewSet)
router.register("enterprise-copilot", views.EnterpriseCopilotSessionViewSet)
router.register("self-healing-incidents", views.SelfHealingGovernanceIncidentViewSet)
router.register("cognitive-snapshots", views.CognitiveCommandCenterSnapshotViewSet)
router.register("work-tools", views.WorkToolDefinitionViewSet)
router.register("tool-assignments", views.EmployeeToolAssignmentViewSet)
router.register("dashboard-configs", views.UnifiedDashboardConfigViewSet)
router.register("work-projects", views.WorkProjectViewSet)
router.register("work-boards", views.WorkBoardViewSet)
router.register("work-items", views.WorkItemViewSet)
router.register("work-comments", views.WorkCommentViewSet)
router.register("work-attachments", views.WorkAttachmentViewSet)
router.register("team-channels", views.TeamChannelViewSet)
router.register("team-messages", views.TeamMessageViewSet)
router.register("work-activity-records", views.WorkActivityRecordViewSet)
router.register("hardware-devices", views.UniversalHardwareDeviceViewSet)
router.register("execution-snapshots", views.ExecutionCommandSnapshotViewSet)

urlpatterns = [
    path("dashboard/", views.dashboard, name="workforce-dashboard"),
    path("command-center/", views.command_center, name="workforce-command-center"),
    path("ecosystem-command-center/", views.ecosystem_command_center, name="workforce-ecosystem-command-center"),
    path("cognitive-command-center/", views.cognitive_command_center, name="workforce-cognitive-command-center"),
    path("unified-work-dashboard/", views.unified_work_dashboard, name="workforce-unified-work-dashboard"),
    path("execution-command-center/", views.execution_command_center, name="workforce-execution-command-center"),
    path("org-tree/", views.org_tree, name="workforce-org-tree"),
    path("self/attendance/", views.self_attendance, name="workforce-self-attendance"),
]
urlpatterns += router.urls
