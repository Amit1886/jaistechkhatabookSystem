from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.platform.workforce.models import AttendanceLog, EmployeeActivityLog, EmployeeProfile, LeaveRequest, StaffKPI, StaffTask


class WorkforceRepository:
    def employee_for_user(self, tenant, user):
        return EmployeeProfile.objects.filter(tenant=tenant, user=user, is_active=True).first()

    def org_tree(self, tenant):
        employees = EmployeeProfile.objects.filter(tenant=tenant, is_active=True).select_related("department", "designation", "reporting_manager")
        return [
            {
                "id": str(emp.id),
                "code": emp.employee_code,
                "name": getattr(emp.user, "get_full_name", lambda: "")() or emp.user.email,
                "department": emp.department.name if emp.department else "",
                "designation": emp.designation.title if emp.designation else "",
                "manager_id": str(emp.reporting_manager_id) if emp.reporting_manager_id else None,
                "type": emp.worker_type,
                "status": emp.lifecycle_status,
            }
            for emp in employees
        ]

    def dashboard(self, tenant):
        employees = EmployeeProfile.objects.filter(tenant=tenant, is_active=True)
        today = timezone.localdate()
        attendance = AttendanceLog.objects.filter(tenant=tenant, logged_at__date=today)
        tasks = StaffTask.objects.filter(tenant=tenant)
        leave = LeaveRequest.objects.filter(tenant=tenant)
        return {
            "active_employees": employees.filter(lifecycle_status="active").count(),
            "total_workers": employees.count(),
            "present_today": attendance.values("employee").distinct().count(),
            "pending_leave": leave.filter(status__in=["review", "approval"]).count(),
            "pending_tasks": tasks.exclude(status__in=["completed", "cancelled"]).count(),
            "completed_tasks": tasks.filter(status="completed").count(),
            "kpi_score": StaffKPI.objects.filter(tenant=tenant).aggregate(total=Sum("current_value")).get("total") or 0,
            "by_department": list(employees.values("department__name").annotate(total=Count("id")).order_by("-total")),
        }

    def log_activity(self, employee, action, **payload):
        return EmployeeActivityLog.objects.create(
            tenant=employee.tenant,
            employee=employee,
            action=action,
            object_type=payload.get("object_type", ""),
            object_id=payload.get("object_id", ""),
            payload=payload,
        )

