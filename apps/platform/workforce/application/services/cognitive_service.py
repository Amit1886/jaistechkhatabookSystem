from decimal import Decimal

from django.db.models import Avg, Count
from django.utils import timezone

from apps.platform.workforce.models import (
    BehavioralSignal,
    CareerGrowthPlan,
    CognitiveCommandCenterSnapshot,
    CognitiveEmployeeProfile,
    EmployeeProfile,
    EmployeeRecognition,
    EmployeeTransparencyRecord,
    EnterpriseCopilotSession,
    HRComplianceLedger,
    OrganizationalGraphEdge,
    OrganizationalGraphNode,
    PayrollRun,
    SelfHealingGovernanceIncident,
)


def _decimal(value, default="0"):
    try:
        return Decimal(str(value if value is not None else default))
    except Exception:
        return Decimal(default)


class CognitiveProfileService:
    def profile_for(self, employee):
        profile, _ = CognitiveEmployeeProfile.objects.get_or_create(tenant=employee.tenant, employee=employee)
        return profile

    def ingest_behavioral_signal(self, *, employee, signal_type, score, confidence=80, source="", evidence=None):
        signal = BehavioralSignal.objects.create(
            tenant=employee.tenant,
            employee=employee,
            signal_type=signal_type,
            score=score,
            confidence=confidence,
            source=source,
            evidence=evidence or {},
        )
        self.recalculate_profile(employee)
        return signal

    def recalculate_profile(self, employee):
        profile = self.profile_for(employee)
        signals = BehavioralSignal.objects.filter(tenant=employee.tenant, employee=employee)
        avg = signals.values("signal_type").annotate(score=Avg("score"))
        scores = {row["signal_type"]: _decimal(row["score"]) for row in avg}

        engagement = scores.get("engagement", Decimal("0"))
        morale = scores.get("morale", Decimal("0"))
        collaboration = scores.get("collaboration", Decimal("0"))
        communication = scores.get("communication", Decimal("0"))
        burnout = scores.get("burnout", Decimal("0"))
        resignation = scores.get("resignation", Decimal("0"))

        profile.engagement_score = engagement
        profile.morale_score = morale
        profile.burnout_risk = burnout
        profile.resignation_probability = resignation
        profile.trust_score = max(Decimal("0"), min(Decimal("100"), (engagement + morale + collaboration) / Decimal("3")))
        profile.leadership_score = max(Decimal("0"), min(Decimal("100"), (collaboration + communication + morale) / Decimal("3")))
        profile.promotion_probability = max(Decimal("0"), min(Decimal("100"), (profile.trust_score + profile.leadership_score - burnout) / Decimal("2")))
        profile.behavioral_analytics = scores
        profile.ai_career_insights = {
            "summary": "Use this profile as a decision-support signal with manager review.",
            "recommended_focus": self._focus_area(profile),
        }
        profile.save()
        return profile

    def _focus_area(self, profile):
        if profile.burnout_risk >= 70:
            return "wellness_and_workload_balance"
        if profile.leadership_score >= 75:
            return "leadership_track"
        if profile.engagement_score < 45:
            return "engagement_recovery"
        return "growth_and_certification"


class TransparencyService:
    def publish_record(self, *, employee, record_type, title, calculation, period=""):
        return EmployeeTransparencyRecord.objects.create(
            tenant=employee.tenant,
            employee=employee,
            record_type=record_type,
            period=period,
            title=title,
            calculation=calculation,
            locked_at=timezone.now(),
        )


class CultureEngagementService:
    def recognize(self, *, employee, title, points=0, given_by=None, program=None, payload=None):
        recognition = EmployeeRecognition.objects.create(
            tenant=employee.tenant,
            employee=employee,
            given_by=given_by,
            program=program,
            title=title,
            points=points,
            payload=payload or {},
        )
        return recognition


class CareerGrowthService:
    def recommend_growth_plan(self, employee):
        profile = CognitiveProfileService().profile_for(employee)
        target_role = "Team Lead" if profile.leadership_score >= 70 else "Senior Specialist"
        plan = CareerGrowthPlan.objects.create(
            tenant=employee.tenant,
            employee=employee,
            target_role=target_role,
            learning_path=[
                "Complete role-specific SOP training",
                "Finish one advanced certification",
                "Run a reviewed project or mentoring assignment",
            ],
            recommended_certifications=profile.certifications or [],
            promotion_readiness=profile.promotion_probability,
            leadership_potential=profile.leadership_score,
            ai_recommendation=profile.ai_career_insights.get("recommended_focus", "growth_and_certification"),
            status="recommended",
        )
        return plan


class ComplianceService:
    def record(self, *, tenant, ledger_type, title, employee=None, payload=None, recorded_by=None):
        raw = f"{tenant_id(tenant)}:{ledger_type}:{title}:{timezone.now().isoformat()}"
        return HRComplianceLedger.objects.create(
            tenant=tenant,
            employee=employee,
            ledger_type=ledger_type,
            title=title,
            payload=payload or {},
            immutable_hash=str(abs(hash(raw))),
            recorded_by=recorded_by,
        )


def tenant_id(tenant):
    return getattr(tenant, "id", tenant)


class OrganizationalGraphService:
    def rebuild_employee_graph(self, tenant):
        for employee in EmployeeProfile.objects.filter(tenant=tenant, is_active=True).select_related("department", "reporting_manager"):
            employee_node, _ = OrganizationalGraphNode.objects.update_or_create(
                tenant=tenant,
                node_type="employee",
                object_id=str(employee.id),
                defaults={"label": employee.employee_code, "metrics": {"worker_type": employee.worker_type}},
            )
            if employee.department:
                dept_node, _ = OrganizationalGraphNode.objects.update_or_create(
                    tenant=tenant,
                    node_type="department",
                    object_id=str(employee.department_id),
                    defaults={"label": employee.department.name, "metrics": {}},
                )
                OrganizationalGraphEdge.objects.update_or_create(
                    tenant=tenant,
                    source=employee_node,
                    target=dept_node,
                    relation_type="belongs_to_department",
                    defaults={"weight": 1, "metrics": {}},
                )
        return OrganizationalGraphNode.objects.filter(tenant=tenant).count()


class EnterpriseCopilotService:
    def ask(self, *, tenant, copilot_type, prompt, user=None, employee=None, context=None):
        response = self._rule_response(copilot_type, prompt)
        return EnterpriseCopilotSession.objects.create(
            tenant=tenant,
            copilot_type=copilot_type,
            prompt=prompt,
            response=response,
            user=user,
            employee=employee,
            context=context or {},
            status="answered",
        )

    def _rule_response(self, copilot_type, prompt):
        prompt = (prompt or "").lower()
        if "payroll" in prompt or copilot_type == "payroll":
            return "Payroll assistant: review salary, incentives, deductions, attendance, and payout status before approval."
        if "attendance" in prompt or copilot_type == "attendance":
            return "Attendance assistant: check late logs, missing checkout, shift mismatch, and verified attendance sources."
        if "burnout" in prompt:
            return "Employee coach: review workload, recent engagement trend, leave balance, and manager intervention notes."
        return "HR assistant: I prepared a governance-safe response. Use this as decision support and keep human approval."


class SelfHealingGovernanceService:
    def scan(self, tenant):
        incidents = []
        payroll_drafts = PayrollRun.objects.filter(tenant=tenant, status="draft").count()
        if payroll_drafts > 3:
            incidents.append(
                SelfHealingGovernanceIncident.objects.create(
                    tenant=tenant,
                    incident_type="payroll",
                    severity="medium",
                    title="Multiple draft payroll runs pending review",
                    detection_payload={"draft_runs": payroll_drafts},
                    triggered_workflow="payroll_review",
                )
            )

        risky_profiles = CognitiveEmployeeProfile.objects.filter(tenant=tenant, burnout_risk__gte=70)
        for profile in risky_profiles[:20]:
            incidents.append(
                SelfHealingGovernanceIncident.objects.create(
                    tenant=tenant,
                    employee=profile.employee,
                    incident_type="burnout",
                    severity="high",
                    title="High burnout risk detected",
                    detection_payload={"burnout_risk": str(profile.burnout_risk)},
                    triggered_workflow="manager_wellness_review",
                )
            )
        return incidents


class CognitiveCommandCenterService:
    def dashboard(self, tenant):
        profile_stats = CognitiveEmployeeProfile.objects.filter(tenant=tenant).aggregate(
            trust=Avg("trust_score"),
            engagement=Avg("engagement_score"),
            morale=Avg("morale_score"),
            burnout=Avg("burnout_risk"),
            promotion=Avg("promotion_probability"),
        )
        open_incidents = SelfHealingGovernanceIncident.objects.filter(tenant=tenant, status="open").count()
        recognitions = EmployeeRecognition.objects.filter(tenant=tenant).count()
        compliance_logs = HRComplianceLedger.objects.filter(tenant=tenant).count()
        graph_nodes = OrganizationalGraphNode.objects.filter(tenant=tenant).count()
        copilot_sessions = EnterpriseCopilotSession.objects.filter(tenant=tenant).count()

        workforce_health = max(Decimal("0"), Decimal("100") - _decimal(profile_stats.get("burnout")))
        snapshot, _ = CognitiveCommandCenterSnapshot.objects.update_or_create(
            tenant=tenant,
            period=timezone.localdate().strftime("%Y-%m"),
            defaults={
                "workforce_health": workforce_health,
                "engagement_score": _decimal(profile_stats.get("engagement")),
                "culture_score": _decimal(profile_stats.get("morale")),
                "payroll_accuracy": Decimal("100"),
                "operational_efficiency": _decimal(profile_stats.get("trust")),
                "profitability_score": _decimal(profile_stats.get("promotion")),
                "ai_insights": [
                    {"type": "burnout", "value": str(profile_stats.get("burnout") or 0)},
                    {"type": "open_governance_incidents", "value": open_incidents},
                ],
            },
        )
        return {
            "snapshot": {
                "period": snapshot.period,
                "workforce_health": snapshot.workforce_health,
                "engagement_score": snapshot.engagement_score,
                "culture_score": snapshot.culture_score,
                "payroll_accuracy": snapshot.payroll_accuracy,
                "operational_efficiency": snapshot.operational_efficiency,
                "profitability_score": snapshot.profitability_score,
                "ai_insights": snapshot.ai_insights,
            },
            "open_incidents": open_incidents,
            "recognitions": recognitions,
            "compliance_logs": compliance_logs,
            "graph_nodes": graph_nodes,
            "copilot_sessions": copilot_sessions,
            "signals_by_type": list(BehavioralSignal.objects.filter(tenant=tenant).values("signal_type").annotate(total=Count("id"))),
        }
