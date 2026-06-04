from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.platform.workforce.models import (
    AttendanceLog,
    EmployeePayrollProfile,
    EmployeeProfile,
    PayrollRun,
    Payslip,
    PayoutInstruction,
    ProductivitySignal,
)


class PayrollCalculationService:
    @transaction.atomic
    def generate_run(self, *, tenant, period, generated_by=None):
        run, _ = PayrollRun.objects.get_or_create(tenant=tenant, period=period, defaults={"generated_by": generated_by})
        totals = {"gross": Decimal("0"), "net": Decimal("0"), "deductions": Decimal("0"), "tax": Decimal("0")}
        for employee in EmployeeProfile.objects.filter(tenant=tenant, is_active=True).select_related("payroll_profile"):
            payslip = self.calculate_payslip(run, employee, period)
            totals["gross"] += payslip.gross_amount
            totals["net"] += payslip.net_amount
            totals["deductions"] += payslip.deduction_amount + payslip.penalty_amount
            totals["tax"] += payslip.tax_amount
        run.totals = {key: str(value) for key, value in totals.items()}
        run.status = PayrollRun.Status.REVIEW
        run.save(update_fields=["totals", "status", "updated_at"])
        return run

    def calculate_payslip(self, run, employee, period):
        payroll = getattr(employee, "payroll_profile", None)
        policy = payroll.policy if payroll else None
        base = Decimal(str(policy.base_amount if policy else employee.salary_structure.get("base_amount", 0)))
        hourly_rate = Decimal(str(policy.hourly_rate if policy else employee.salary_structure.get("hourly_rate", 0)))
        task_rate = Decimal(str(policy.task_rate if policy else employee.salary_structure.get("task_rate", 0)))
        active_seconds = ProductivitySignal.objects.filter(employee=employee, captured_at__date__startswith=period[:7]).aggregate(total=Sum("duration_seconds")).get("total") or 0
        task_count = employee.tasks.filter(status="completed", updated_at__date__startswith=period[:7]).count()
        overtime_minutes = AttendanceLog.objects.filter(employee=employee, logged_at__date__startswith=period[:7]).aggregate(total=Sum("overtime_minutes")).get("total") or 0
        penalty_minutes = AttendanceLog.objects.filter(employee=employee, logged_at__date__startswith=period[:7]).aggregate(total=Sum("penalty_minutes")).get("total") or 0
        hourly = Decimal(active_seconds) / Decimal("3600") * hourly_rate
        task_pay = Decimal(task_count) * task_rate
        overtime = Decimal(overtime_minutes) / Decimal("60") * hourly_rate * Decimal("1.5")
        penalty = Decimal(penalty_minutes) / Decimal("60") * hourly_rate
        incentive = Decimal(str(employee.incentive_model.get("fixed_incentive", 0)))
        bonus = Decimal(str(employee.incentive_model.get("performance_bonus", 0)))
        tax = self._tax(base + hourly + task_pay + overtime + incentive + bonus, policy)
        gross = base + hourly + task_pay + overtime + incentive + bonus
        net = gross - penalty - tax
        payslip, _ = Payslip.objects.update_or_create(
            tenant=employee.tenant,
            payroll_run=run,
            employee=employee,
            defaults={
                "gross_amount": gross,
                "incentive_amount": incentive,
                "overtime_amount": overtime,
                "bonus_amount": bonus,
                "penalty_amount": penalty,
                "tax_amount": tax,
                "net_amount": net,
                "line_items": [
                    {"type": "base", "amount": str(base)},
                    {"type": "hourly", "amount": str(hourly)},
                    {"type": "task", "amount": str(task_pay)},
                    {"type": "overtime", "amount": str(overtime)},
                    {"type": "penalty", "amount": str(penalty)},
                    {"type": "tax", "amount": str(tax)},
                ],
            },
        )
        return payslip

    def _tax(self, amount, policy):
        rules = policy.tax_rules if policy else {}
        rate = Decimal(str(rules.get("flat_rate_percent", 0)))
        return amount * rate / Decimal("100")


class PayoutService:
    def queue_payout(self, payslip):
        profile = getattr(payslip.employee, "payroll_profile", None)
        method = "upi" if profile and profile.upi_id else "bank"
        destination = {
            "upi_id": getattr(profile, "upi_id", ""),
            "bank_name": getattr(profile, "bank_name", ""),
            "account_number": getattr(profile, "account_number", ""),
            "ifsc": getattr(profile, "ifsc", ""),
        }
        return PayoutInstruction.objects.create(tenant=payslip.tenant, payslip=payslip, method=method, destination=destination)
