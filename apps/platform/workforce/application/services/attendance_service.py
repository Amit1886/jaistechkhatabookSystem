from django.utils import timezone

from apps.platform.core.application.services.event_service import EventService
from apps.platform.workforce.infrastructure.repositories.workforce_repository import WorkforceRepository
from apps.platform.workforce.models import AttendanceLog, ShiftAssignment


class AttendanceService:
    def __init__(self, repository=None, event_service=None):
        self.repository = repository or WorkforceRepository()
        self.event_service = event_service or EventService()

    def mark(self, *, employee, log_type, method="manual", latitude=None, longitude=None, selfie=None, device_fingerprint="", logged_at=None):
        logged_at = logged_at or timezone.now()
        shift = self.current_shift(employee, logged_at.date())
        log = AttendanceLog.objects.create(
            tenant=employee.tenant,
            employee=employee,
            shift=shift,
            log_type=log_type,
            method=method,
            latitude=latitude,
            longitude=longitude,
            selfie=selfie,
            device_fingerprint=device_fingerprint,
            logged_at=logged_at,
            verification_status="verified" if method in {"biometric", "qr"} else "pending",
        )
        self.apply_rules(log)
        self.repository.log_activity(employee, "attendance_marked", object_type="attendance_log", object_id=str(log.id), method=method)
        self.event_service.publish("attendance_marked", {"employee_id": str(employee.id), "log_id": str(log.id), "method": method}, tenant=employee.tenant, user=employee.user)
        return log

    def current_shift(self, employee, date):
        assignment = (
            ShiftAssignment.objects.filter(tenant=employee.tenant, employee=employee, starts_at__lte=date)
            .filter(ends_at__isnull=True)
            .select_related("shift")
            .first()
        )
        return assignment.shift if assignment else None

    def apply_rules(self, log):
        if not log.shift or log.log_type != "in":
            return log
        shift_start = timezone.datetime.combine(log.logged_at.date(), log.shift.start_time, tzinfo=log.logged_at.tzinfo)
        late_minutes = max(int((log.logged_at - shift_start).total_seconds() // 60) - int(log.shift.grace_minutes or 0), 0)
        log.penalty_minutes = late_minutes
        log.save(update_fields=["penalty_minutes", "updated_at"])
        return log

