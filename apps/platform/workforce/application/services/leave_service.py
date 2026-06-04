from apps.platform.core.application.services.event_service import EventService
from apps.platform.workforce.models import LeaveRequest


class LeaveService:
    def __init__(self, event_service=None):
        self.event_service = event_service or EventService()

    def apply(self, *, employee, leave_type, starts_on, ends_on, reason=""):
        leave = LeaveRequest.objects.create(
            tenant=employee.tenant,
            employee=employee,
            leave_type=leave_type,
            starts_on=starts_on,
            ends_on=ends_on,
            reason=reason,
            status=LeaveRequest.Status.REVIEW,
            approver=employee.reporting_manager,
        )
        self.event_service.publish("leave_requested", {"leave_id": str(leave.id), "employee_id": str(employee.id)}, tenant=employee.tenant, user=employee.user)
        return leave

    def decide(self, leave, status, approver=None, note=""):
        leave.status = status
        leave.approver = approver or leave.approver
        leave.decision_note = note
        leave.save(update_fields=["status", "approver", "decision_note", "updated_at"])
        self.event_service.publish("leave_decided", {"leave_id": str(leave.id), "status": status}, tenant=leave.tenant, user=approver)
        return leave

