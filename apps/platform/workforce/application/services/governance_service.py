from decimal import Decimal

from django.db.models import Avg, Sum

from apps.platform.core.application.services.event_service import EventService
from apps.platform.workforce.models import (
    DisciplineCase,
    EmployeeScoreSnapshot,
    FraudRiskSignal,
    HRInsight,
    ProductivitySignal,
    WorkforceProfitabilitySnapshot,
)


class ProductivityScoringService:
    def __init__(self, event_service=None):
        self.event_service = event_service or EventService()

    def record_signal(self, *, employee, signal_type, score, source="", weight=100, duration_seconds=0, evidence=None):
        signal = ProductivitySignal.objects.create(
            tenant=employee.tenant,
            employee=employee,
            signal_type=signal_type,
            source=source,
            score=score,
            weight=weight,
            duration_seconds=duration_seconds,
            evidence=evidence or {},
        )
        self.event_service.publish("productivity_signal_recorded", {"employee_id": str(employee.id), "signal_type": signal_type}, tenant=employee.tenant, user=employee.user)
        return signal

    def calculate_scores(self, employee, period):
        signals = ProductivitySignal.objects.filter(tenant=employee.tenant, employee=employee, captured_at__date__startswith=period[:7])
        avg_score = signals.aggregate(value=Avg("score")).get("value") or Decimal("0")
        active_seconds = signals.aggregate(value=Sum("duration_seconds")).get("value") or 0
        fraud = FraudRiskSignal.objects.filter(tenant=employee.tenant, employee=employee, status="open").aggregate(value=Avg("risk_score")).get("value") or Decimal("0")
        discipline_count = DisciplineCase.objects.filter(tenant=employee.tenant, employee=employee).exclude(status="cancelled").count()
        discipline_score = max(Decimal("100") - Decimal(discipline_count * 10), Decimal("0"))
        trust_score = max(Decimal("100") - Decimal(fraud), Decimal("0"))
        performance = (Decimal(avg_score) * Decimal("0.45")) + (discipline_score * Decimal("0.20")) + (trust_score * Decimal("0.20")) + Decimal("15")
        snapshot, _ = EmployeeScoreSnapshot.objects.update_or_create(
            tenant=employee.tenant,
            employee=employee,
            period=period,
            defaults={
                "productivity_score": avg_score,
                "discipline_score": discipline_score,
                "trust_score": trust_score,
                "leadership_score": employee.metadata.get("leadership_score", 0),
                "communication_score": employee.metadata.get("communication_score", 0),
                "quality_score": employee.metadata.get("quality_score", avg_score),
                "fraud_risk_score": fraud,
                "performance_score": min(performance, Decimal("100")),
                "details": {"active_seconds": active_seconds, "signal_count": signals.count()},
            },
        )
        return snapshot


class FraudDetectionService:
    def detect(self, employee, evidence):
        risks = []
        if evidence.get("gps_distance_jump_km", 0) > 5:
            risks.append(("gps_spoofing", 80))
        if evidence.get("duplicate_hash"):
            risks.append(("duplicate_work", 70))
        if evidence.get("idle_ratio", 0) > 0.5:
            risks.append(("suspicious_pattern", 60))
        created = []
        for risk_type, score in risks:
            created.append(
                FraudRiskSignal.objects.create(
                    tenant=employee.tenant,
                    employee=employee,
                    risk_type=risk_type,
                    risk_score=score,
                    evidence=evidence,
                )
            )
        return created


class DisciplineService:
    def open_case(self, *, employee, violation_type, action="warning", severity="medium", description="", evidence=None, penalty_amount=0):
        return DisciplineCase.objects.create(
            tenant=employee.tenant,
            employee=employee,
            violation_type=violation_type,
            action=action,
            severity=severity,
            description=description,
            evidence=evidence or {},
            penalty_amount=penalty_amount,
            status="review",
        )


class HRIntelligenceService:
    def generate_insights(self, employee, score_snapshot=None):
        score_snapshot = score_snapshot or EmployeeScoreSnapshot.objects.filter(employee=employee).order_by("-created_at").first()
        insights = []
        if score_snapshot and score_snapshot.performance_score < 45:
            insights.append(("training", 75, "Training recommended", "Performance score is below threshold."))
        if score_snapshot and score_snapshot.fraud_risk_score > 60:
            insights.append(("burnout", 60, "Manager review recommended", "High risk signals detected; review context before action."))
        if score_snapshot and score_snapshot.performance_score > 85 and score_snapshot.trust_score > 80:
            insights.append(("promotion", 70, "Promotion candidate", "Strong performance and trust score."))
        created = []
        for insight_type, confidence, title, recommendation in insights:
            created.append(
                HRInsight.objects.create(
                    tenant=employee.tenant,
                    employee=employee,
                    insight_type=insight_type,
                    confidence=confidence,
                    title=title,
                    recommendation=recommendation,
                )
            )
        return created


class WorkforceProfitabilityService:
    def snapshot(self, *, tenant, period, employee=None, department=None, revenue=0, payroll_cost=0, support_efficiency=0, sales_efficiency=0):
        revenue = Decimal(str(revenue or 0))
        payroll_cost = Decimal(str(payroll_cost or 0))
        roi = ((revenue - payroll_cost) / payroll_cost * Decimal("100")) if payroll_cost else Decimal("0")
        return WorkforceProfitabilitySnapshot.objects.create(
            tenant=tenant,
            period=period,
            employee=employee,
            department=department,
            revenue=revenue,
            payroll_cost=payroll_cost,
            support_efficiency=support_efficiency,
            sales_efficiency=sales_efficiency,
            roi=roi,
        )

