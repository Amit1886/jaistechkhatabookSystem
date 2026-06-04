from decimal import Decimal

from django.db.models import Count

from apps.platform.core.application.services.event_service import EventService
from apps.platform.workforce.models import (
    Certification,
    EmployeeProfile,
    EmployeeWallet,
    GigTask,
    BusinessNetworkNode,
    MarketplaceListing,
    MarketplaceApplication,
    PartnerProfile,
    PartnerSettlement,
    RemoteActivityEvent,
    RemoteWorkSession,
    TrainingCourse,
    WalletTransaction,
)


class RemoteWorkforceService:
    def __init__(self, event_service=None):
        self.event_service = event_service or EventService()

    def start_session(self, employee, project_key=""):
        session = RemoteWorkSession.objects.create(tenant=employee.tenant, employee=employee, project_key=project_key)
        self.event_service.publish("remote_session_started", {"session_id": str(session.id), "employee_id": str(employee.id)}, tenant=employee.tenant, user=employee.user)
        return session

    def record_event(self, session, event_type, payload=None, risk_score=0):
        event = RemoteActivityEvent.objects.create(tenant=session.tenant, session=session, event_type=event_type, payload=payload or {}, risk_score=risk_score)
        self.update_authenticity(session)
        return event

    def update_authenticity(self, session):
        events = session.events.all()
        risk_total = sum(Decimal(str(event.risk_score or 0)) for event in events)
        count = max(events.count(), 1)
        session.authenticity_score = max(Decimal("100") - (risk_total / Decimal(count)), Decimal("0"))
        session.activity_score = min(Decimal(events.count() * 10), Decimal("100"))
        session.save(update_fields=["authenticity_score", "activity_score", "updated_at"])
        return session


class AITaskDistributionService:
    def assign(self, gig: GigTask):
        candidates = EmployeeProfile.objects.filter(tenant=gig.tenant, is_active=True).exclude(lifecycle_status="exited")
        best = None
        best_score = Decimal("-1")
        required = set(gig.required_skills or [])
        for employee in candidates:
            skills = set((employee.metadata or {}).get("skills", []))
            skill_score = Decimal(len(required.intersection(skills)) * 20)
            workload = employee.gig_tasks.exclude(status__in=["completed", "cancelled"]).count()
            workload_score = max(Decimal("50") - Decimal(workload * 10), Decimal("0"))
            worker_match = Decimal("20") if employee.worker_type in {"freelancer", "gig", "field", "delivery", "remote"} else Decimal("5")
            score = skill_score + workload_score + worker_match
            if score > best_score:
                best = employee
                best_score = score
        if best:
            gig.assignee = best
            gig.assignment_score = best_score
            gig.status = GigTask.Status.ASSIGNED
            gig.save(update_fields=["assignee", "assignment_score", "status", "updated_at"])
        return gig


class MarketplaceService:
    def apply(self, listing, applicant=None, agency_name="", proposal="", quoted_amount=0):
        return MarketplaceApplication.objects.create(
            tenant=listing.tenant,
            listing=listing,
            applicant=applicant,
            agency_name=agency_name,
            proposal=proposal,
            quoted_amount=quoted_amount,
        )


class PartnerOperationsService:
    def onboard_partner(self, *, tenant, name, partner_type, owner=None, territory=None, white_label_config=None):
        return PartnerProfile.objects.create(
            tenant=tenant,
            name=name,
            partner_type=partner_type,
            owner=owner,
            territory=territory or {},
            white_label_config=white_label_config or {},
            onboarding_status="review",
        )

    def settle(self, partner, period, revenue):
        revenue = Decimal(str(revenue or 0))
        commission_percent = Decimal(str((partner.commission_rules or {}).get("percent", 0)))
        share_percent = Decimal(str((partner.revenue_share_rules or {}).get("percent", 0)))
        commission = revenue * commission_percent / Decimal("100")
        revenue_share = revenue * share_percent / Decimal("100")
        return PartnerSettlement.objects.create(
            tenant=partner.tenant,
            partner=partner,
            period=period,
            revenue=revenue,
            commission=commission,
            revenue_share=revenue_share,
            payable=commission + revenue_share,
            status="review",
        )


class TrainingCertificationService:
    def enroll(self, course: TrainingCourse, employee):
        cert, _ = Certification.objects.get_or_create(tenant=course.tenant, course=course, employee=employee)
        return cert

    def complete(self, certification, score):
        certification.score = score
        certification.status = "certified" if Decimal(str(score)) >= certification.course.passing_score else "failed"
        certification.save(update_fields=["score", "status", "updated_at"])
        return certification


class WalletRewardService:
    def wallet_for(self, employee):
        wallet, _ = EmployeeWallet.objects.get_or_create(tenant=employee.tenant, employee=employee)
        return wallet

    def credit(self, employee, amount=0, points=0, transaction_type="earning", source_type="", source_id="", note=""):
        wallet = self.wallet_for(employee)
        wallet.balance += Decimal(str(amount or 0))
        wallet.reward_points += int(points or 0)
        wallet.save(update_fields=["balance", "reward_points", "updated_at"])
        return WalletTransaction.objects.create(
            tenant=employee.tenant,
            wallet=wallet,
            transaction_type=transaction_type,
            amount=amount,
            points=points,
            source_type=source_type,
            source_id=source_id,
            note=note,
        )


class EcosystemDashboardService:
    def dashboard(self, tenant):
        return {
            "open_gigs": GigTask.objects.filter(tenant=tenant, status="open").count(),
            "assigned_gigs": GigTask.objects.filter(tenant=tenant, status="assigned").count(),
            "remote_sessions": RemoteWorkSession.objects.filter(tenant=tenant, ended_at__isnull=True).count(),
            "partners": PartnerProfile.objects.filter(tenant=tenant, is_active=True).count(),
            "marketplace_applications": MarketplaceApplication.objects.filter(tenant=tenant).count(),
            "certifications": list(Certification.objects.filter(tenant=tenant).values("status").annotate(total=Count("id"))),
            "wallet_liability": sum(wallet.balance + wallet.bonus_balance for wallet in EmployeeWallet.objects.filter(tenant=tenant)),
            "open_marketplace": MarketplaceListing.objects.filter(tenant=tenant, status="open").count(),
            "pending_settlements": PartnerSettlement.objects.filter(tenant=tenant, status__in=["draft", "review"]).count(),
            "network_nodes": BusinessNetworkNode.objects.filter(tenant=tenant).count(),
        }
