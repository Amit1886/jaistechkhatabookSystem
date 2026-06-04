from rest_framework import serializers

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
    EmployeeWallet,
    EmployeeToolAssignment,
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


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"


class DesignationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Designation
        fields = "__all__"


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = "__all__"


class EmployeeProfileSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = EmployeeProfile
        fields = "__all__"


class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = "__all__"


class ShiftAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftAssignment
        fields = "__all__"


class AttendanceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceLog
        fields = "__all__"


class LeaveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = "__all__"


class StaffTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffTask
        fields = "__all__"


class StaffKPISerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffKPI
        fields = "__all__"


class EmployeeDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeDevice
        fields = "__all__"


class EmployeeSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeSession
        fields = "__all__"


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeDocument
        fields = "__all__"


class EmployeeActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeActivityLog
        fields = "__all__"
        read_only_fields = fields


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = "__all__"


class StaffDiscussionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffDiscussion
        fields = "__all__"


class ProductivitySignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductivitySignal
        fields = "__all__"


class EmployeeScoreSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeScoreSnapshot
        fields = "__all__"


class PayrollPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollPolicy
        fields = "__all__"


class EmployeePayrollProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeePayrollProfile
        fields = "__all__"


class PayrollRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollRun
        fields = "__all__"


class PayslipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payslip
        fields = "__all__"


class PayoutInstructionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutInstruction
        fields = "__all__"


class DisciplineCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisciplineCase
        fields = "__all__"


class FraudRiskSignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudRiskSignal
        fields = "__all__"


class HRInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = HRInsight
        fields = "__all__"


class WorkforceProfitabilitySnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkforceProfitabilitySnapshot
        fields = "__all__"


class RemoteWorkSessionSerializer(serializers.ModelSerializer):
    employee_display = serializers.CharField(source="employee.employee_code", read_only=True)

    class Meta:
        model = RemoteWorkSession
        fields = "__all__"


class RemoteActivityEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = RemoteActivityEvent
        fields = "__all__"


class GigTaskSerializer(serializers.ModelSerializer):
    assignee_display = serializers.CharField(source="assignee.employee_code", read_only=True)

    class Meta:
        model = GigTask
        fields = "__all__"


class MarketplaceListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketplaceListing
        fields = "__all__"


class MarketplaceApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketplaceApplication
        fields = "__all__"


class PartnerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerProfile
        fields = "__all__"


class PartnerSettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerSettlement
        fields = "__all__"


class TrainingCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingCourse
        fields = "__all__"


class CertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certification
        fields = "__all__"


class EmployeeWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeWallet
        fields = "__all__"


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = "__all__"


class BusinessNetworkNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessNetworkNode
        fields = "__all__"


class CognitiveEmployeeProfileSerializer(serializers.ModelSerializer):
    employee_display = serializers.CharField(source="employee.employee_code", read_only=True)

    class Meta:
        model = CognitiveEmployeeProfile
        fields = "__all__"


class BehavioralSignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = BehavioralSignal
        fields = "__all__"


class EmployeeTransparencyRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeTransparencyRecord
        fields = "__all__"


class CultureEngagementProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = CultureEngagementProgram
        fields = "__all__"


class EmployeeRecognitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeRecognition
        fields = "__all__"


class CareerGrowthPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = CareerGrowthPlan
        fields = "__all__"


class HRComplianceLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = HRComplianceLedger
        fields = "__all__"
        read_only_fields = fields


class OrganizationalGraphNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationalGraphNode
        fields = "__all__"


class OrganizationalGraphEdgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationalGraphEdge
        fields = "__all__"


class EnterpriseCopilotSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnterpriseCopilotSession
        fields = "__all__"


class SelfHealingGovernanceIncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SelfHealingGovernanceIncident
        fields = "__all__"


class CognitiveCommandCenterSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = CognitiveCommandCenterSnapshot
        fields = "__all__"


class WorkToolDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkToolDefinition
        fields = "__all__"


class EmployeeToolAssignmentSerializer(serializers.ModelSerializer):
    tool_name = serializers.CharField(source="tool.name", read_only=True)
    tool_route = serializers.CharField(source="tool.route", read_only=True)

    class Meta:
        model = EmployeeToolAssignment
        fields = "__all__"


class UnifiedDashboardConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnifiedDashboardConfig
        fields = "__all__"


class WorkProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkProject
        fields = "__all__"


class WorkBoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkBoard
        fields = "__all__"


class WorkItemSerializer(serializers.ModelSerializer):
    assignee_display = serializers.CharField(source="assignee.employee_code", read_only=True)

    class Meta:
        model = WorkItem
        fields = "__all__"


class WorkCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkComment
        fields = "__all__"


class WorkAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkAttachment
        fields = "__all__"


class TeamChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamChannel
        fields = "__all__"


class TeamMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMessage
        fields = "__all__"


class WorkActivityRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkActivityRecord
        fields = "__all__"


class UniversalHardwareDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UniversalHardwareDevice
        fields = "__all__"


class ExecutionCommandSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExecutionCommandSnapshot
        fields = "__all__"
