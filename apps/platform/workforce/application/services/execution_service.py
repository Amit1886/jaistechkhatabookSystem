from decimal import Decimal

from django.db.models import Avg, Count, Sum
from django.utils import timezone

from apps.platform.workforce.models import (
    AttendanceLog,
    CognitiveEmployeeProfile,
    EmployeeProfile,
    EmployeeToolAssignment,
    ExecutionCommandSnapshot,
    FraudRiskSignal,
    GigTask,
    HRInsight,
    Payslip,
    RemoteWorkSession,
    SelfHealingGovernanceIncident,
    StaffTask,
    UniversalHardwareDevice,
    UnifiedDashboardConfig,
    WorkActivityRecord,
    WorkItem,
    WorkProject,
    WorkToolDefinition,
)


DEFAULT_TOOL_BLUEPRINTS = {
    "support": [
        ("support_tickets", "Support Tickets", "support", "/support/tickets/"),
        ("remote_troubleshooting", "Remote Troubleshooting", "support", "/support/remote/"),
        ("bug_tracker", "Bug Tracker", "support", "/support/bugs/"),
        ("sla_tracker", "SLA Tracker", "support", "/support/sla/"),
    ],
    "sales": [
        ("crm_dashboard", "CRM Dashboard", "sales", "/crm/"),
        ("lead_manager", "Lead Manager", "sales", "/leads/"),
        ("quotation_generator", "Quotation Generator", "sales", "/commerce/quotations/"),
        ("commission_tracker", "Commission Tracker", "sales", "/commission/"),
    ],
    "hr": [
        ("hiring_pipeline", "Hiring Pipeline", "hr", "/superadmin/platform_workforce/publicworkforceapplication/"),
        ("attendance_manager", "Attendance Manager", "hr", "/api/v1/platform/workforce/attendance/"),
        ("payroll_manager", "Payroll Manager", "hr", "/api/v1/platform/workforce/payroll-runs/"),
        ("performance_reviews", "Performance Reviews", "hr", "/api/v1/platform/workforce/cognitive-profiles/"),
    ],
    "accounting": [
        ("ledger_manager", "Ledger Manager", "accounting", "/ledger/"),
        ("gst_billing", "GST Billing", "accounting", "/api/v1/platform/tax/"),
        ("eway_bill", "E-Way Bill", "accounting", "/api/v1/platform/tax/eway-bills/"),
        ("payment_approvals", "Payment Approvals", "accounting", "/payments/"),
    ],
    "marketing": [
        ("campaign_manager", "Campaign Manager", "marketing", "/api/v1/marketing/"),
        ("seo_tracker", "SEO Tracker", "marketing", "/marketing/seo/"),
        ("content_workflow", "Content Workflow", "marketing", "/marketing/content/"),
        ("ad_spend", "Ad Spend", "marketing", "/marketing/spend/"),
    ],
    "remote": [
        ("work_timer", "Work Timer", "remote", "/api/v1/platform/workforce/remote-sessions/"),
        ("screenshot_tracker", "Screenshot Tracker", "remote", "/remote/screenshots/"),
        ("webcam_verification", "Webcam Verification", "remote", "/remote/webcam/"),
        ("activity_monitor", "Activity Monitor", "remote", "/api/v1/platform/workforce/remote-activity/"),
    ],
    "field": [
        ("gps_tracking", "GPS Tracking", "field", "/api/v1/location/"),
        ("route_optimizer", "Route Optimizer", "field", "/delivery/routes/"),
        ("visit_tracker", "Visit Tracker", "field", "/field/visits/"),
        ("mobile_attendance", "Mobile Attendance", "field", "/api/v1/platform/workforce/self/attendance/"),
    ],
    "gig": [
        ("gig_marketplace", "Gig Marketplace", "gig", "/api/v1/platform/workforce/gig-tasks/"),
        ("task_submission", "Task Submission", "gig", "/gig/submissions/"),
        ("wallet", "Wallet and Payouts", "gig", "/api/v1/platform/workforce/wallets/"),
        ("trust_score", "AI Trust Score", "gig", "/api/v1/platform/workforce/cognitive-profiles/"),
    ],
}


class ToolAssignmentService:
    def ensure_default_tools(self, tenant):
        created = []
        for audience, tools in DEFAULT_TOOL_BLUEPRINTS.items():
            for key, name, category, route in tools:
                tool, _ = WorkToolDefinition.objects.update_or_create(
                    tenant=tenant,
                    key=key,
                    defaults={
                        "name": name,
                        "category": category,
                        "route": route,
                        "role_rules": {"audience": audience},
                        "required_permissions": [],
                    },
                )
                created.append(tool)
        return created

    def assign_for_employee(self, employee):
        self.ensure_default_tools(employee.tenant)
        audiences = self._audiences_for(employee)
        tools = WorkToolDefinition.objects.filter(tenant=employee.tenant, role_rules__audience__in=audiences)
        assignments = []
        for tool in tools:
            assignment, _ = EmployeeToolAssignment.objects.update_or_create(
                tenant=employee.tenant,
                employee=employee,
                tool=tool,
                defaults={"source": "role_rule", "enabled": True},
            )
            assignments.append(assignment)
        return assignments

    def _audiences_for(self, employee):
        values = {employee.worker_type or "employee", "project"}
        dept_key = getattr(getattr(employee, "department", None), "key", "") or ""
        role_text = f"{employee.worker_type} {dept_key} {getattr(getattr(employee, 'designation', None), 'key', '')}".lower()
        if "support" in role_text:
            values.add("support")
        if "sales" in role_text:
            values.add("sales")
        if "hr" in role_text or "human" in role_text:
            values.add("hr")
        if "account" in role_text or "finance" in role_text:
            values.add("accounting")
        if "market" in role_text:
            values.add("marketing")
        if employee.worker_type in {"remote", "freelancer", "consultant"}:
            values.add("remote")
        if employee.worker_type in {"field", "delivery"}:
            values.add("field")
        if employee.worker_type in {"gig", "freelancer"}:
            values.add("gig")
        return values


class UnifiedWorkDashboardService:
    def dashboard_for(self, *, tenant, user=None, employee=None):
        if employee:
            ToolAssignmentService().assign_for_employee(employee)
        tools = EmployeeToolAssignment.objects.filter(tenant=tenant, enabled=True)
        if employee:
            tools = tools.filter(employee=employee)

        work_items = WorkItem.objects.filter(tenant=tenant)
        if employee:
            work_items = work_items.filter(assignee=employee)

        staff_tasks = StaffTask.objects.filter(tenant=tenant)
        if employee:
            staff_tasks = staff_tasks.filter(assignee=employee)

        return {
            "employee": getattr(employee, "employee_code", ""),
            "tools": list(tools.select_related("tool").values("tool__key", "tool__name", "tool__category", "tool__route", "config")[:40]),
            "work_items": list(work_items.values("id", "work_type", "title", "status", "priority", "due_at")[:30]),
            "staff_tasks": list(staff_tasks.values("id", "title", "status", "priority", "due_at")[:20]),
            "attendance": list(AttendanceLog.objects.filter(tenant=tenant, employee=employee).values("log_type", "method", "logged_at", "verification_status")[:10]) if employee else [],
            "payroll": list(Payslip.objects.filter(tenant=tenant, employee=employee).values("status", "gross_amount", "net_amount", "payroll_run__period")[:10]) if employee else [],
            "gig_tasks": list(GigTask.objects.filter(tenant=tenant, assignee=employee).values("title", "status", "payout_amount")[:10]) if employee else [],
            "ai_profile": self._ai_profile(employee) if employee else {},
            "config": self._dashboard_config(tenant, employee),
        }

    def _ai_profile(self, employee):
        profile = CognitiveEmployeeProfile.objects.filter(tenant=employee.tenant, employee=employee).first()
        if not profile:
            return {}
        return {
            "trust_score": profile.trust_score,
            "productivity_history": profile.productivity_history,
            "burnout_risk": profile.burnout_risk,
            "promotion_probability": profile.promotion_probability,
            "leadership_score": profile.leadership_score,
        }

    def _dashboard_config(self, tenant, employee):
        qs = UnifiedDashboardConfig.objects.filter(tenant=tenant, is_active=True)
        if employee:
            candidate = qs.filter(audience__worker_type=employee.worker_type).first()
            if candidate:
                return {"title": candidate.title, "widgets": candidate.widgets, "layout": candidate.layout}
        candidate = qs.filter(key="default").first()
        return {"title": getattr(candidate, "title", "Unified Work Dashboard"), "widgets": getattr(candidate, "widgets", []), "layout": getattr(candidate, "layout", {})}


class WorkExecutionService:
    def create_work_item(self, *, tenant, title, work_type="task", assignee=None, reporter=None, payload=None):
        return WorkItem.objects.create(
            tenant=tenant,
            title=title,
            work_type=work_type,
            assignee=assignee,
            reporter=reporter,
            payload=payload or {},
            status="draft",
        )

    def record_activity(self, *, tenant, employee=None, work_item=None, activity_type="work", duration_seconds=0, evidence=None):
        quality = Decimal(str((evidence or {}).get("quality_score", 0)))
        productivity = Decimal(str((evidence or {}).get("productivity_score", 0)))
        fraud = Decimal(str((evidence or {}).get("fraud_risk_score", 0)))
        return WorkActivityRecord.objects.create(
            tenant=tenant,
            employee=employee,
            work_item=work_item,
            activity_type=activity_type,
            duration_seconds=duration_seconds,
            quality_score=quality,
            productivity_score=productivity,
            fraud_risk_score=fraud,
            evidence=evidence or {},
        )


class ExecutionCommandCenterService:
    def dashboard(self, tenant):
        active_work = WorkItem.objects.filter(tenant=tenant).exclude(status__in=["completed", "cancelled"]).count()
        support_tickets = WorkItem.objects.filter(tenant=tenant, work_type__in=["ticket", "bug"]).exclude(status__in=["completed", "cancelled"]).count()
        sales = WorkItem.objects.filter(tenant=tenant, work_type="lead").exclude(status__in=["completed", "cancelled"]).count()
        remote = RemoteWorkSession.objects.filter(tenant=tenant, ended_at__isnull=True).count()
        payroll_projection = Payslip.objects.filter(tenant=tenant).aggregate(total=Sum("net_amount")).get("total") or Decimal("0")
        ai_alerts = (
            FraudRiskSignal.objects.filter(tenant=tenant, status="open").count()
            + HRInsight.objects.filter(tenant=tenant, status="open").count()
            + SelfHealingGovernanceIncident.objects.filter(tenant=tenant, status="open").count()
        )
        workload = WorkItem.objects.filter(tenant=tenant).values("assignee").annotate(total=Count("id"))
        avg_load = sum(row["total"] for row in workload) / max(len(workload), 1)
        balance = max(Decimal("0"), Decimal("100") - Decimal(str(avg_load * 5)))

        snapshot, _ = ExecutionCommandSnapshot.objects.update_or_create(
            tenant=tenant,
            period=timezone.localdate().strftime("%Y-%m-%d"),
            defaults={
                "live_employees": RemoteWorkSession.objects.filter(tenant=tenant, ended_at__isnull=True).values("employee").distinct().count(),
                "active_work_items": active_work,
                "support_tickets": support_tickets,
                "sales_activities": sales,
                "remote_sessions": remote,
                "field_locations": WorkActivityRecord.objects.filter(tenant=tenant, activity_type__in=["gps", "visit"]).count(),
                "payroll_projection": payroll_projection,
                "ai_alerts": ai_alerts,
                "workload_balance_score": balance,
                "payload": {
                    "productivity_avg": str(WorkActivityRecord.objects.filter(tenant=tenant).aggregate(avg=Avg("productivity_score")).get("avg") or 0),
                    "hardware_online": UniversalHardwareDevice.objects.filter(tenant=tenant, status="active").count(),
                },
            },
        )
        return {
            "snapshot": {
                "live_employees": snapshot.live_employees,
                "active_work_items": snapshot.active_work_items,
                "support_tickets": snapshot.support_tickets,
                "sales_activities": snapshot.sales_activities,
                "remote_sessions": snapshot.remote_sessions,
                "field_locations": snapshot.field_locations,
                "payroll_projection": snapshot.payroll_projection,
                "ai_alerts": snapshot.ai_alerts,
                "workload_balance_score": snapshot.workload_balance_score,
                "payload": snapshot.payload,
            },
            "work_by_type": list(WorkItem.objects.filter(tenant=tenant).values("work_type").annotate(total=Count("id"))),
            "work_by_status": list(WorkItem.objects.filter(tenant=tenant).values("status").annotate(total=Count("id"))),
            "recent_activity": list(WorkActivityRecord.objects.filter(tenant=tenant).values("employee__employee_code", "activity_type", "productivity_score", "fraud_risk_score", "started_at")[:30]),
        }
