from rest_framework import permissions, status, viewsets
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.platform.workforce.application.services.attendance_service import AttendanceService
from apps.platform.workforce.application.services.dashboard_service import WorkforceDashboardService
from apps.platform.workforce.application.services.cognitive_service import (
    CareerGrowthService,
    CognitiveCommandCenterService,
    CognitiveProfileService,
    CultureEngagementService,
    EnterpriseCopilotService,
    OrganizationalGraphService,
    SelfHealingGovernanceService,
    TransparencyService,
)
from apps.platform.workforce.application.services.ecosystem_service import (
    AITaskDistributionService,
    EcosystemDashboardService,
    MarketplaceService,
    PartnerOperationsService,
    RemoteWorkforceService,
    TrainingCertificationService,
    WalletRewardService,
)
from apps.platform.workforce.application.services.execution_service import (
    ExecutionCommandCenterService,
    ToolAssignmentService,
    UnifiedWorkDashboardService,
    WorkExecutionService,
)
from apps.platform.workforce.application.services.leave_service import LeaveService
from apps.platform.workforce.interfaces.api.serializers import (
    AnnouncementSerializer,
    AttendanceLogSerializer,
    BehavioralSignalSerializer,
    BusinessNetworkNodeSerializer,
    CareerGrowthPlanSerializer,
    CertificationSerializer,
    CognitiveCommandCenterSnapshotSerializer,
    CognitiveEmployeeProfileSerializer,
    CultureEngagementProgramSerializer,
    DepartmentSerializer,
    DesignationSerializer,
    DisciplineCaseSerializer,
    EmployeeActivityLogSerializer,
    EmployeeDeviceSerializer,
    EmployeeDocumentSerializer,
    EmployeePayrollProfileSerializer,
    EmployeeProfileSerializer,
    EmployeeRecognitionSerializer,
    EmployeeScoreSnapshotSerializer,
    EmployeeSessionSerializer,
    EmployeeTransparencyRecordSerializer,
    EmployeeWalletSerializer,
    EmployeeToolAssignmentSerializer,
    EnterpriseCopilotSessionSerializer,
    ExecutionCommandSnapshotSerializer,
    FraudRiskSignalSerializer,
    HRComplianceLedgerSerializer,
    GigTaskSerializer,
    HRInsightSerializer,
    LeaveRequestSerializer,
    MarketplaceApplicationSerializer,
    MarketplaceListingSerializer,
    OrganizationalGraphEdgeSerializer,
    OrganizationalGraphNodeSerializer,
    PayrollPolicySerializer,
    PayrollRunSerializer,
    PartnerProfileSerializer,
    PartnerSettlementSerializer,
    PayoutInstructionSerializer,
    PayslipSerializer,
    ProductivitySignalSerializer,
    RemoteActivityEventSerializer,
    RemoteWorkSessionSerializer,
    SelfHealingGovernanceIncidentSerializer,
    ShiftAssignmentSerializer,
    ShiftSerializer,
    StaffDiscussionSerializer,
    StaffKPISerializer,
    StaffTaskSerializer,
    TeamSerializer,
    TeamChannelSerializer,
    TeamMessageSerializer,
    TrainingCourseSerializer,
    UnifiedDashboardConfigSerializer,
    UniversalHardwareDeviceSerializer,
    WalletTransactionSerializer,
    WorkActivityRecordSerializer,
    WorkAttachmentSerializer,
    WorkBoardSerializer,
    WorkCommentSerializer,
    WorkItemSerializer,
    WorkProjectSerializer,
    WorkToolDefinitionSerializer,
    WorkforceProfitabilitySnapshotSerializer,
)
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
    HRComplianceLedger,
    GigTask,
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


class WorkforcePermission(permissions.IsAuthenticated):
    pass


class TenantScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [WorkforcePermission]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant")
        if tenant_id and hasattr(qs.model, "tenant"):
            qs = qs.filter(tenant_id=tenant_id)
        return qs


class DepartmentViewSet(TenantScopedViewSet):
    queryset = Department.objects.select_related("tenant", "company", "branch", "parent").all()
    serializer_class = DepartmentSerializer


class DesignationViewSet(TenantScopedViewSet):
    queryset = Designation.objects.select_related("tenant").all()
    serializer_class = DesignationSerializer


class TeamViewSet(TenantScopedViewSet):
    queryset = Team.objects.select_related("tenant", "department", "manager").prefetch_related("members").all()
    serializer_class = TeamSerializer


class EmployeeProfileViewSet(TenantScopedViewSet):
    queryset = EmployeeProfile.objects.select_related("tenant", "user", "company", "branch", "department", "designation", "reporting_manager").all()
    serializer_class = EmployeeProfileSerializer

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        from apps.platform.workforce.application.services.workforce_service import WorkforceService

        employee = WorkforceService().transition_lifecycle(self.get_object(), request.data.get("status"), actor=request.user)
        return Response(self.get_serializer(employee).data)


class ShiftViewSet(TenantScopedViewSet):
    queryset = Shift.objects.select_related("tenant").all()
    serializer_class = ShiftSerializer


class ShiftAssignmentViewSet(TenantScopedViewSet):
    queryset = ShiftAssignment.objects.select_related("tenant", "employee", "shift").all()
    serializer_class = ShiftAssignmentSerializer


class AttendanceLogViewSet(TenantScopedViewSet):
    queryset = AttendanceLog.objects.select_related("tenant", "employee", "shift").all()
    serializer_class = AttendanceLogSerializer


class LeaveRequestViewSet(TenantScopedViewSet):
    queryset = LeaveRequest.objects.select_related("tenant", "employee", "approver").all()
    serializer_class = LeaveRequestSerializer

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        leave = LeaveService().decide(self.get_object(), request.data.get("status"), approver=request.user, note=request.data.get("note", ""))
        return Response(self.get_serializer(leave).data)


class StaffTaskViewSet(TenantScopedViewSet):
    queryset = StaffTask.objects.select_related("tenant", "assignee", "assigned_by").all()
    serializer_class = StaffTaskSerializer


class StaffKPIViewSet(TenantScopedViewSet):
    queryset = StaffKPI.objects.select_related("tenant", "employee").all()
    serializer_class = StaffKPISerializer


class EmployeeDeviceViewSet(TenantScopedViewSet):
    queryset = EmployeeDevice.objects.select_related("tenant", "employee").all()
    serializer_class = EmployeeDeviceSerializer


class EmployeeSessionViewSet(TenantScopedViewSet):
    queryset = EmployeeSession.objects.select_related("tenant", "employee", "device").all()
    serializer_class = EmployeeSessionSerializer


class EmployeeDocumentViewSet(TenantScopedViewSet):
    queryset = EmployeeDocument.objects.select_related("tenant", "employee").all()
    serializer_class = EmployeeDocumentSerializer


class EmployeeActivityLogViewSet(TenantScopedViewSet):
    queryset = EmployeeActivityLog.objects.select_related("tenant", "employee").all()
    serializer_class = EmployeeActivityLogSerializer
    http_method_names = ["get", "head", "options"]


class AnnouncementViewSet(TenantScopedViewSet):
    queryset = Announcement.objects.select_related("tenant", "created_by").all()
    serializer_class = AnnouncementSerializer


class StaffDiscussionViewSet(TenantScopedViewSet):
    queryset = StaffDiscussion.objects.select_related("tenant", "department", "task", "created_by").all()
    serializer_class = StaffDiscussionSerializer


class ProductivitySignalViewSet(TenantScopedViewSet):
    queryset = ProductivitySignal.objects.select_related("tenant", "employee").all()
    serializer_class = ProductivitySignalSerializer


class EmployeeScoreSnapshotViewSet(TenantScopedViewSet):
    queryset = EmployeeScoreSnapshot.objects.select_related("tenant", "employee").all()
    serializer_class = EmployeeScoreSnapshotSerializer


class PayrollPolicyViewSet(TenantScopedViewSet):
    queryset = PayrollPolicy.objects.select_related("tenant").all()
    serializer_class = PayrollPolicySerializer


class EmployeePayrollProfileViewSet(TenantScopedViewSet):
    queryset = EmployeePayrollProfile.objects.select_related("tenant", "employee", "policy").all()
    serializer_class = EmployeePayrollProfileSerializer


class PayrollRunViewSet(TenantScopedViewSet):
    queryset = PayrollRun.objects.select_related("tenant", "generated_by").all()
    serializer_class = PayrollRunSerializer

    @action(detail=False, methods=["post"])
    def generate(self, request):
        from apps.platform.workforce.application.services.payroll_service import PayrollCalculationService

        tenant = getattr(request, "identity_tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
        run = PayrollCalculationService().generate_run(tenant=tenant, period=request.data.get("period"), generated_by=request.user)
        return Response(self.get_serializer(run).data)


class PayslipViewSet(TenantScopedViewSet):
    queryset = Payslip.objects.select_related("tenant", "payroll_run", "employee").all()
    serializer_class = PayslipSerializer

    @action(detail=True, methods=["post"])
    def queue_payout(self, request, pk=None):
        from apps.platform.workforce.application.services.payroll_service import PayoutService

        payout = PayoutService().queue_payout(self.get_object())
        return Response(PayoutInstructionSerializer(payout).data)


class PayoutInstructionViewSet(TenantScopedViewSet):
    queryset = PayoutInstruction.objects.select_related("tenant", "payslip").all()
    serializer_class = PayoutInstructionSerializer


class DisciplineCaseViewSet(TenantScopedViewSet):
    queryset = DisciplineCase.objects.select_related("tenant", "employee").all()
    serializer_class = DisciplineCaseSerializer


class FraudRiskSignalViewSet(TenantScopedViewSet):
    queryset = FraudRiskSignal.objects.select_related("tenant", "employee").all()
    serializer_class = FraudRiskSignalSerializer


class HRInsightViewSet(TenantScopedViewSet):
    queryset = HRInsight.objects.select_related("tenant", "employee").all()
    serializer_class = HRInsightSerializer


class WorkforceProfitabilitySnapshotViewSet(TenantScopedViewSet):
    queryset = WorkforceProfitabilitySnapshot.objects.select_related("tenant", "department", "employee").all()
    serializer_class = WorkforceProfitabilitySnapshotSerializer


class RemoteWorkSessionViewSet(TenantScopedViewSet):
    queryset = RemoteWorkSession.objects.select_related("tenant", "employee").all()
    serializer_class = RemoteWorkSessionSerializer

    @action(detail=False, methods=["post"])
    def start(self, request):
        tenant = getattr(request, "identity_tenant", None)
        employee = EmployeeProfile.objects.filter(tenant=tenant, user=request.user, is_active=True).first()
        if not employee:
            return Response({"detail": "Employee profile not found."}, status=status.HTTP_404_NOT_FOUND)
        session = RemoteWorkforceService().start_session(employee, project_key=request.data.get("project_key", ""))
        return Response(self.get_serializer(session).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def record_event(self, request, pk=None):
        event = RemoteWorkforceService().record_event(
            self.get_object(),
            event_type=request.data.get("event_type", "task_update"),
            payload=request.data.get("payload", {}),
            risk_score=request.data.get("risk_score", 0),
        )
        return Response(RemoteActivityEventSerializer(event).data, status=status.HTTP_201_CREATED)


class RemoteActivityEventViewSet(TenantScopedViewSet):
    queryset = RemoteActivityEvent.objects.select_related("tenant", "session", "session__employee").all()
    serializer_class = RemoteActivityEventSerializer


class GigTaskViewSet(TenantScopedViewSet):
    queryset = GigTask.objects.select_related("tenant", "posted_by", "assignee").all()
    serializer_class = GigTaskSerializer

    @action(detail=True, methods=["post"])
    def ai_assign(self, request, pk=None):
        gig = AITaskDistributionService().assign(self.get_object())
        return Response(self.get_serializer(gig).data)

    @action(detail=True, methods=["post"])
    def reward_assignee(self, request, pk=None):
        gig = self.get_object()
        if not gig.assignee:
            return Response({"detail": "Gig has no assignee."}, status=status.HTTP_400_BAD_REQUEST)
        transaction = WalletRewardService().credit(
            gig.assignee,
            amount=request.data.get("amount", gig.payout_amount),
            points=request.data.get("points", 0),
            transaction_type="gig_reward",
            source_type="gig_task",
            source_id=str(gig.id),
            note=request.data.get("note", gig.title),
        )
        return Response(WalletTransactionSerializer(transaction).data, status=status.HTTP_201_CREATED)


class MarketplaceListingViewSet(TenantScopedViewSet):
    queryset = MarketplaceListing.objects.select_related("tenant", "published_by").all()
    serializer_class = MarketplaceListingSerializer


class MarketplaceApplicationViewSet(TenantScopedViewSet):
    queryset = MarketplaceApplication.objects.select_related("tenant", "listing", "applicant").all()
    serializer_class = MarketplaceApplicationSerializer

    @action(detail=False, methods=["post"])
    def apply(self, request):
        tenant = getattr(request, "identity_tenant", None)
        listing = get_object_or_404(MarketplaceListing, pk=request.data.get("listing"), tenant=tenant)
        applicant_id = request.data.get("applicant")
        applicant = EmployeeProfile.objects.filter(pk=applicant_id, tenant=tenant).first() if applicant_id else None
        application = MarketplaceService().apply(
            listing,
            applicant=applicant,
            agency_name=request.data.get("agency_name", ""),
            proposal=request.data.get("proposal", ""),
            quoted_amount=request.data.get("quoted_amount", 0),
        )
        return Response(self.get_serializer(application).data, status=status.HTTP_201_CREATED)


class PartnerProfileViewSet(TenantScopedViewSet):
    queryset = PartnerProfile.objects.select_related("tenant", "owner").all()
    serializer_class = PartnerProfileSerializer

    @action(detail=True, methods=["post"])
    def settle(self, request, pk=None):
        settlement = PartnerOperationsService().settle(
            self.get_object(),
            period=request.data.get("period"),
            revenue=request.data.get("revenue", 0),
        )
        return Response(PartnerSettlementSerializer(settlement).data, status=status.HTTP_201_CREATED)


class PartnerSettlementViewSet(TenantScopedViewSet):
    queryset = PartnerSettlement.objects.select_related("tenant", "partner").all()
    serializer_class = PartnerSettlementSerializer


class TrainingCourseViewSet(TenantScopedViewSet):
    queryset = TrainingCourse.objects.select_related("tenant").all()
    serializer_class = TrainingCourseSerializer

    @action(detail=True, methods=["post"])
    def enroll(self, request, pk=None):
        tenant = getattr(request, "identity_tenant", None)
        employee = get_object_or_404(EmployeeProfile, pk=request.data.get("employee"), tenant=tenant)
        certification = TrainingCertificationService().enroll(self.get_object(), employee)
        return Response(CertificationSerializer(certification).data, status=status.HTTP_201_CREATED)


class CertificationViewSet(TenantScopedViewSet):
    queryset = Certification.objects.select_related("tenant", "course", "employee").all()
    serializer_class = CertificationSerializer

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        certification = TrainingCertificationService().complete(self.get_object(), request.data.get("score", 0))
        return Response(self.get_serializer(certification).data)


class EmployeeWalletViewSet(TenantScopedViewSet):
    queryset = EmployeeWallet.objects.select_related("tenant", "employee").all()
    serializer_class = EmployeeWalletSerializer


class WalletTransactionViewSet(TenantScopedViewSet):
    queryset = WalletTransaction.objects.select_related("tenant", "wallet", "wallet__employee").all()
    serializer_class = WalletTransactionSerializer


class BusinessNetworkNodeViewSet(TenantScopedViewSet):
    queryset = BusinessNetworkNode.objects.select_related("tenant", "parent", "linked_tenant").all()
    serializer_class = BusinessNetworkNodeSerializer


class CognitiveEmployeeProfileViewSet(TenantScopedViewSet):
    queryset = CognitiveEmployeeProfile.objects.select_related("tenant", "employee").all()
    serializer_class = CognitiveEmployeeProfileSerializer

    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        profile = CognitiveProfileService().recalculate_profile(self.get_object().employee)
        return Response(self.get_serializer(profile).data)


class BehavioralSignalViewSet(TenantScopedViewSet):
    queryset = BehavioralSignal.objects.select_related("tenant", "employee").all()
    serializer_class = BehavioralSignalSerializer

    @action(detail=False, methods=["post"])
    def ingest(self, request):
        tenant = getattr(request, "identity_tenant", None)
        employee = get_object_or_404(EmployeeProfile, pk=request.data.get("employee"), tenant=tenant)
        signal = CognitiveProfileService().ingest_behavioral_signal(
            employee=employee,
            signal_type=request.data.get("signal_type", "engagement"),
            score=request.data.get("score", 0),
            confidence=request.data.get("confidence", 80),
            source=request.data.get("source", "manual"),
            evidence=request.data.get("evidence", {}),
        )
        return Response(self.get_serializer(signal).data, status=status.HTTP_201_CREATED)


class EmployeeTransparencyRecordViewSet(TenantScopedViewSet):
    queryset = EmployeeTransparencyRecord.objects.select_related("tenant", "employee").all()
    serializer_class = EmployeeTransparencyRecordSerializer

    @action(detail=False, methods=["post"])
    def publish(self, request):
        tenant = getattr(request, "identity_tenant", None)
        employee = get_object_or_404(EmployeeProfile, pk=request.data.get("employee"), tenant=tenant)
        record = TransparencyService().publish_record(
            employee=employee,
            record_type=request.data.get("record_type", "performance"),
            title=request.data.get("title", "Transparency record"),
            calculation=request.data.get("calculation", {}),
            period=request.data.get("period", ""),
        )
        return Response(self.get_serializer(record).data, status=status.HTTP_201_CREATED)


class CultureEngagementProgramViewSet(TenantScopedViewSet):
    queryset = CultureEngagementProgram.objects.select_related("tenant").all()
    serializer_class = CultureEngagementProgramSerializer


class EmployeeRecognitionViewSet(TenantScopedViewSet):
    queryset = EmployeeRecognition.objects.select_related("tenant", "employee", "given_by", "program").all()
    serializer_class = EmployeeRecognitionSerializer

    @action(detail=False, methods=["post"])
    def recognize(self, request):
        tenant = getattr(request, "identity_tenant", None)
        employee = get_object_or_404(EmployeeProfile, pk=request.data.get("employee"), tenant=tenant)
        recognition = CultureEngagementService().recognize(
            employee=employee,
            title=request.data.get("title", "Recognition"),
            points=request.data.get("points", 0),
            given_by=request.user,
            payload=request.data.get("payload", {}),
        )
        return Response(self.get_serializer(recognition).data, status=status.HTTP_201_CREATED)


class CareerGrowthPlanViewSet(TenantScopedViewSet):
    queryset = CareerGrowthPlan.objects.select_related("tenant", "employee").all()
    serializer_class = CareerGrowthPlanSerializer

    @action(detail=False, methods=["post"])
    def recommend(self, request):
        tenant = getattr(request, "identity_tenant", None)
        employee = get_object_or_404(EmployeeProfile, pk=request.data.get("employee"), tenant=tenant)
        plan = CareerGrowthService().recommend_growth_plan(employee)
        return Response(self.get_serializer(plan).data, status=status.HTTP_201_CREATED)


class HRComplianceLedgerViewSet(TenantScopedViewSet):
    queryset = HRComplianceLedger.objects.select_related("tenant", "employee", "recorded_by").all()
    serializer_class = HRComplianceLedgerSerializer
    http_method_names = ["get", "head", "options"]


class OrganizationalGraphNodeViewSet(TenantScopedViewSet):
    queryset = OrganizationalGraphNode.objects.select_related("tenant").all()
    serializer_class = OrganizationalGraphNodeSerializer

    @action(detail=False, methods=["post"])
    def rebuild(self, request):
        tenant = getattr(request, "identity_tenant", None)
        total = OrganizationalGraphService().rebuild_employee_graph(tenant)
        return Response({"status": "rebuilt", "nodes": total})


class OrganizationalGraphEdgeViewSet(TenantScopedViewSet):
    queryset = OrganizationalGraphEdge.objects.select_related("tenant", "source", "target").all()
    serializer_class = OrganizationalGraphEdgeSerializer


class EnterpriseCopilotSessionViewSet(TenantScopedViewSet):
    queryset = EnterpriseCopilotSession.objects.select_related("tenant", "employee", "user").all()
    serializer_class = EnterpriseCopilotSessionSerializer

    @action(detail=False, methods=["post"])
    def ask(self, request):
        tenant = getattr(request, "identity_tenant", None)
        employee_id = request.data.get("employee")
        employee = EmployeeProfile.objects.filter(pk=employee_id, tenant=tenant).first() if employee_id else None
        session = EnterpriseCopilotService().ask(
            tenant=tenant,
            copilot_type=request.data.get("copilot_type", "hr"),
            prompt=request.data.get("prompt", ""),
            user=request.user,
            employee=employee,
            context=request.data.get("context", {}),
        )
        return Response(self.get_serializer(session).data, status=status.HTTP_201_CREATED)


class SelfHealingGovernanceIncidentViewSet(TenantScopedViewSet):
    queryset = SelfHealingGovernanceIncident.objects.select_related("tenant", "employee").all()
    serializer_class = SelfHealingGovernanceIncidentSerializer

    @action(detail=False, methods=["post"])
    def scan(self, request):
        tenant = getattr(request, "identity_tenant", None)
        incidents = SelfHealingGovernanceService().scan(tenant)
        return Response(self.get_serializer(incidents, many=True).data, status=status.HTTP_201_CREATED)


class CognitiveCommandCenterSnapshotViewSet(TenantScopedViewSet):
    queryset = CognitiveCommandCenterSnapshot.objects.select_related("tenant").all()
    serializer_class = CognitiveCommandCenterSnapshotSerializer


class WorkToolDefinitionViewSet(TenantScopedViewSet):
    queryset = WorkToolDefinition.objects.select_related("tenant").all()
    serializer_class = WorkToolDefinitionSerializer

    @action(detail=False, methods=["post"])
    def seed_defaults(self, request):
        tenant = getattr(request, "identity_tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
        tools = ToolAssignmentService().ensure_default_tools(tenant)
        return Response(self.get_serializer(tools, many=True).data, status=status.HTTP_201_CREATED)


class EmployeeToolAssignmentViewSet(TenantScopedViewSet):
    queryset = EmployeeToolAssignment.objects.select_related("tenant", "employee", "tool").all()
    serializer_class = EmployeeToolAssignmentSerializer

    @action(detail=False, methods=["post"])
    def assign_for_employee(self, request):
        tenant = getattr(request, "identity_tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
        employee = get_object_or_404(EmployeeProfile, pk=request.data.get("employee"), tenant=tenant)
        assignments = ToolAssignmentService().assign_for_employee(employee)
        return Response(self.get_serializer(assignments, many=True).data, status=status.HTTP_201_CREATED)


class UnifiedDashboardConfigViewSet(TenantScopedViewSet):
    queryset = UnifiedDashboardConfig.objects.select_related("tenant").all()
    serializer_class = UnifiedDashboardConfigSerializer


class WorkProjectViewSet(TenantScopedViewSet):
    queryset = WorkProject.objects.select_related("tenant", "owner", "department").all()
    serializer_class = WorkProjectSerializer


class WorkBoardViewSet(TenantScopedViewSet):
    queryset = WorkBoard.objects.select_related("tenant", "project").all()
    serializer_class = WorkBoardSerializer


class WorkItemViewSet(TenantScopedViewSet):
    queryset = WorkItem.objects.select_related("tenant", "project", "board", "parent", "assignee", "reporter").all()
    serializer_class = WorkItemSerializer

    @action(detail=False, methods=["post"])
    def quick_create(self, request):
        tenant = getattr(request, "identity_tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
        assignee_id = request.data.get("assignee")
        assignee = EmployeeProfile.objects.filter(pk=assignee_id, tenant=tenant).first() if assignee_id else None
        item = WorkExecutionService().create_work_item(
            tenant=tenant,
            title=request.data.get("title", "Untitled work"),
            work_type=request.data.get("work_type", "task"),
            assignee=assignee,
            reporter=request.user,
            payload=request.data.get("payload", {}),
        )
        return Response(self.get_serializer(item).data, status=status.HTTP_201_CREATED)


class WorkCommentViewSet(TenantScopedViewSet):
    queryset = WorkComment.objects.select_related("tenant", "work_item", "author").all()
    serializer_class = WorkCommentSerializer


class WorkAttachmentViewSet(TenantScopedViewSet):
    queryset = WorkAttachment.objects.select_related("tenant", "work_item", "uploaded_by").all()
    serializer_class = WorkAttachmentSerializer


class TeamChannelViewSet(TenantScopedViewSet):
    queryset = TeamChannel.objects.select_related("tenant", "project").prefetch_related("members").all()
    serializer_class = TeamChannelSerializer


class TeamMessageViewSet(TenantScopedViewSet):
    queryset = TeamMessage.objects.select_related("tenant", "channel", "sender").all()
    serializer_class = TeamMessageSerializer


class WorkActivityRecordViewSet(TenantScopedViewSet):
    queryset = WorkActivityRecord.objects.select_related("tenant", "employee", "work_item").all()
    serializer_class = WorkActivityRecordSerializer

    @action(detail=False, methods=["post"])
    def record(self, request):
        tenant = getattr(request, "identity_tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
        employee_id = request.data.get("employee")
        item_id = request.data.get("work_item")
        employee = EmployeeProfile.objects.filter(pk=employee_id, tenant=tenant).first() if employee_id else None
        item = WorkItem.objects.filter(pk=item_id, tenant=tenant).first() if item_id else None
        record = WorkExecutionService().record_activity(
            tenant=tenant,
            employee=employee,
            work_item=item,
            activity_type=request.data.get("activity_type", "work"),
            duration_seconds=request.data.get("duration_seconds", 0),
            evidence=request.data.get("evidence", {}),
        )
        return Response(self.get_serializer(record).data, status=status.HTTP_201_CREATED)


class UniversalHardwareDeviceViewSet(TenantScopedViewSet):
    queryset = UniversalHardwareDevice.objects.select_related("tenant", "assigned_employee").all()
    serializer_class = UniversalHardwareDeviceSerializer


class ExecutionCommandSnapshotViewSet(TenantScopedViewSet):
    queryset = ExecutionCommandSnapshot.objects.select_related("tenant").all()
    serializer_class = ExecutionCommandSnapshotSerializer


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def dashboard(request):
    tenant = getattr(request, "identity_tenant", None)
    if tenant is None:
        return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(WorkforceDashboardService().dashboard(tenant))


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def command_center(request):
    tenant = getattr(request, "identity_tenant", None)
    if tenant is None:
        return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {
            "dashboard": WorkforceDashboardService().dashboard(tenant),
            "fraud_alerts": FraudRiskSignal.objects.filter(tenant=tenant, status="open").count(),
            "burnout_alerts": HRInsight.objects.filter(tenant=tenant, insight_type="burnout", status="open").count(),
            "live_payroll_estimates": list(Payslip.objects.filter(tenant=tenant).values("employee__employee_code", "net_amount")[:20]),
            "productivity_trends": list(EmployeeScoreSnapshot.objects.filter(tenant=tenant).values("period", "performance_score", "productivity_score")[:50]),
        }
    )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def ecosystem_command_center(request):
    tenant = getattr(request, "identity_tenant", None)
    if tenant is None:
        return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(EcosystemDashboardService().dashboard(tenant))


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def cognitive_command_center(request):
    tenant = getattr(request, "identity_tenant", None)
    if tenant is None:
        return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(CognitiveCommandCenterService().dashboard(tenant))


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def unified_work_dashboard(request):
    tenant = getattr(request, "identity_tenant", None)
    if tenant is None:
        return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
    employee = EmployeeProfile.objects.filter(tenant=tenant, user=request.user, is_active=True).first()
    return Response(UnifiedWorkDashboardService().dashboard_for(tenant=tenant, user=request.user, employee=employee))


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def execution_command_center(request):
    tenant = getattr(request, "identity_tenant", None)
    if tenant is None:
        return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(ExecutionCommandCenterService().dashboard(tenant))


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def org_tree(request):
    tenant = getattr(request, "identity_tenant", None)
    if tenant is None:
        return Response([], status=status.HTTP_200_OK)
    return Response(WorkforceDashboardService().org_tree(tenant))


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def self_attendance(request):
    tenant = getattr(request, "identity_tenant", None)
    employee = EmployeeProfile.objects.filter(tenant=tenant, user=request.user, is_active=True).first()
    if not employee:
        return Response({"detail": "Employee profile not found."}, status=status.HTTP_404_NOT_FOUND)
    log = AttendanceService().mark(
        employee=employee,
        log_type=request.data.get("log_type", "in"),
        method=request.data.get("method", "manual"),
        latitude=request.data.get("latitude"),
        longitude=request.data.get("longitude"),
        device_fingerprint=request.data.get("device_fingerprint", ""),
    )
    return Response(AttendanceLogSerializer(log).data, status=status.HTTP_201_CREATED)
