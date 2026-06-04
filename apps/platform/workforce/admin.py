from django.contrib import admin

from apps.platform.workforce.models import (
    Announcement,
    AttendanceLog,
    BehavioralSignal,
    BusinessNetworkNode,
    CareerGrowthPlan,
    Certification,
    CognitiveCommandCenterSnapshot,
    CognitiveEmployeeProfile,
    CultureEngagementProgram,
    Department,
    Designation,
    DisciplineCase,
    EmployeeActivityLog,
    EmployeeDevice,
    EmployeeDocument,
    EmployeePayrollProfile,
    EmployeeProfile,
    EmployeeRecognition,
    EmployeeScoreSnapshot,
    EmployeeSession,
    EmployeeTransparencyRecord,
    EmployeeToolAssignment,
    EmployeeWallet,
    EnterpriseCopilotSession,
    ExecutionCommandSnapshot,
    FraudRiskSignal,
    GigTask,
    HRComplianceLedger,
    HRInsight,
    LeaveRequest,
    MarketplaceApplication,
    MarketplaceListing,
    OrganizationalGraphEdge,
    OrganizationalGraphNode,
    PayrollPolicy,
    PayrollRun,
    PartnerProfile,
    PartnerSettlement,
    PayoutInstruction,
    Payslip,
    ProductivitySignal,
    PublicWorkforceApplication,
    RemoteActivityEvent,
    RemoteWorkSession,
    SelfHealingGovernanceIncident,
    Shift,
    ShiftAssignment,
    StaffDiscussion,
    StaffKPI,
    StaffTask,
    Team,
    TeamChannel,
    TeamMessage,
    TrainingCourse,
    UnifiedDashboardConfig,
    UniversalHardwareDevice,
    WalletTransaction,
    WorkActivityRecord,
    WorkAttachment,
    WorkBoard,
    WorkComment,
    WorkItem,
    WorkProject,
    WorkToolDefinition,
    WorkforceProfitabilitySnapshot,
)


class TenantAdmin(admin.ModelAdmin):
    list_filter = ("tenant", "is_active")


@admin.register(PublicWorkforceApplication)
class PublicWorkforceApplicationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "full_name", "mobile", "applicant_type", "city", "role_interest", "status")
    list_filter = ("applicant_type", "status", "city", "created_at")
    search_fields = ("full_name", "mobile", "email", "city", "role_interest", "skills", "referral_code")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Department)
class DepartmentAdmin(TenantAdmin):
    list_display = ("name", "key", "company", "branch", "parent", "tenant", "is_active")
    search_fields = ("name", "key", "cost_center")


@admin.register(Designation)
class DesignationAdmin(TenantAdmin):
    list_display = ("title", "key", "level", "tenant", "is_active")
    search_fields = ("title", "key")


@admin.register(Team)
class TeamAdmin(TenantAdmin):
    list_display = ("name", "key", "department", "manager", "tenant", "is_active")
    search_fields = ("name", "key", "manager__email")


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(TenantAdmin):
    list_display = ("employee_code", "user", "worker_type", "lifecycle_status", "department", "designation", "reporting_manager", "tenant")
    search_fields = ("employee_code", "user__email", "user__username")
    list_filter = ("worker_type", "lifecycle_status", "department", "tenant", "is_active")


@admin.register(Shift)
class ShiftAdmin(TenantAdmin):
    list_display = ("code", "name", "start_time", "end_time", "grace_minutes", "tenant", "is_active")
    search_fields = ("code", "name")


@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(TenantAdmin):
    list_display = ("employee", "shift", "starts_at", "ends_at", "tenant", "is_active")
    list_filter = ("shift", "tenant", "is_active")


@admin.register(AttendanceLog)
class AttendanceLogAdmin(TenantAdmin):
    list_display = ("logged_at", "employee", "log_type", "method", "verification_status", "penalty_minutes", "overtime_minutes", "tenant")
    search_fields = ("employee__employee_code", "employee__user__email", "device_fingerprint")
    list_filter = ("log_type", "method", "verification_status", "tenant", "logged_at")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(TenantAdmin):
    list_display = ("employee", "leave_type", "starts_on", "ends_on", "status", "approver", "tenant")
    search_fields = ("employee__employee_code", "reason")
    list_filter = ("status", "leave_type", "tenant", "starts_on")


@admin.register(StaffTask)
class StaffTaskAdmin(TenantAdmin):
    list_display = ("title", "assignee", "assigned_by", "status", "priority", "due_at", "tenant")
    search_fields = ("title", "assignee__employee_code", "assigned_by__email")
    list_filter = ("status", "priority", "tenant", "due_at")


@admin.register(StaffKPI)
class StaffKPIAdmin(TenantAdmin):
    list_display = ("employee", "key", "name", "target_value", "current_value", "period", "weight", "tenant")
    search_fields = ("key", "name", "employee__employee_code")
    list_filter = ("period", "tenant", "is_active")


@admin.register(EmployeeDevice)
class EmployeeDeviceAdmin(TenantAdmin):
    list_display = ("employee", "name", "fingerprint", "status", "last_seen_at", "ip_address", "tenant")
    search_fields = ("employee__employee_code", "fingerprint", "name", "ip_address")
    list_filter = ("status", "tenant", "is_active")


@admin.register(EmployeeSession)
class EmployeeSessionAdmin(TenantAdmin):
    list_display = ("employee", "session_key", "device", "started_at", "last_seen_at", "ended_at", "is_online", "tenant")
    search_fields = ("employee__employee_code", "session_key")
    list_filter = ("is_online", "tenant", "started_at")


@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(TenantAdmin):
    list_display = ("employee", "document_type", "title", "verification_status", "expires_on", "tenant")
    search_fields = ("employee__employee_code", "title", "document_type")
    list_filter = ("document_type", "verification_status", "tenant", "expires_on")


@admin.register(EmployeeActivityLog)
class EmployeeActivityLogAdmin(TenantAdmin):
    list_display = ("recorded_at", "employee", "action", "object_type", "object_id", "tenant")
    search_fields = ("employee__employee_code", "action", "object_id")
    list_filter = ("action", "tenant", "recorded_at")
    readonly_fields = tuple(field.name for field in EmployeeActivityLog._meta.fields)


@admin.register(Announcement)
class AnnouncementAdmin(TenantAdmin):
    list_display = ("title", "created_by", "published_at", "tenant", "is_active")
    search_fields = ("title", "message", "created_by__email")
    list_filter = ("published_at", "tenant", "is_active")


@admin.register(StaffDiscussion)
class StaffDiscussionAdmin(TenantAdmin):
    list_display = ("subject", "discussion_type", "department", "task", "created_by", "is_anonymous", "tenant")
    search_fields = ("subject", "created_by__email", "ai_summary")
    list_filter = ("discussion_type", "is_anonymous", "tenant", "is_active")


for model in (
    ProductivitySignal,
    EmployeeScoreSnapshot,
    PayrollPolicy,
    EmployeePayrollProfile,
    PayrollRun,
    Payslip,
    PayoutInstruction,
    DisciplineCase,
    FraudRiskSignal,
    HRInsight,
    WorkforceProfitabilitySnapshot,
    RemoteWorkSession,
    RemoteActivityEvent,
    GigTask,
    MarketplaceListing,
    MarketplaceApplication,
    PartnerProfile,
    PartnerSettlement,
    TrainingCourse,
    Certification,
    EmployeeWallet,
    WalletTransaction,
    BusinessNetworkNode,
    CognitiveEmployeeProfile,
    BehavioralSignal,
    EmployeeTransparencyRecord,
    CultureEngagementProgram,
    EmployeeRecognition,
    CareerGrowthPlan,
    HRComplianceLedger,
    OrganizationalGraphNode,
    OrganizationalGraphEdge,
    EnterpriseCopilotSession,
    SelfHealingGovernanceIncident,
    CognitiveCommandCenterSnapshot,
    WorkToolDefinition,
    EmployeeToolAssignment,
    UnifiedDashboardConfig,
    WorkProject,
    WorkBoard,
    WorkItem,
    WorkComment,
    WorkAttachment,
    TeamChannel,
    TeamMessage,
    WorkActivityRecord,
    UniversalHardwareDevice,
    ExecutionCommandSnapshot,
):
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
