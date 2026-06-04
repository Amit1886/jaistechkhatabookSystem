from django.db import transaction

from apps.platform.core.application.services.event_service import EventService
from apps.platform.identity.models import EnterprisePermission, EnterpriseRole, RolePermission
from apps.platform.workforce.infrastructure.repositories.workforce_repository import WorkforceRepository
from apps.platform.workforce.models import EmployeeProfile, StaffKPI, StaffTask


class WorkforceService:
    def __init__(self, repository=None, event_service=None):
        self.repository = repository or WorkforceRepository()
        self.event_service = event_service or EventService()

    @transaction.atomic
    def create_employee(self, *, tenant, user, employee_code, worker_type="employee", company=None, branch=None, department=None, designation=None, manager=None):
        profile = EmployeeProfile.objects.create(
            tenant=tenant,
            user=user,
            employee_code=employee_code,
            worker_type=worker_type,
            company=company,
            branch=branch,
            department=department,
            designation=designation,
            reporting_manager=manager,
        )
        self.repository.log_activity(profile, "employee_created")
        self.event_service.publish("employee_created", {"employee_id": str(profile.id), "worker_type": worker_type}, tenant=tenant, user=user)
        return profile

    def transition_lifecycle(self, employee, status, actor=None):
        before = employee.lifecycle_status
        employee.lifecycle_status = status
        employee.save(update_fields=["lifecycle_status", "updated_at"])
        self.repository.log_activity(employee, "employee_lifecycle_changed", before=before, after=status)
        self.event_service.publish("employee_lifecycle_changed", {"employee_id": str(employee.id), "before": before, "after": status}, tenant=employee.tenant, user=actor)
        return employee

    def assign_task(self, *, tenant, assignee, title, assigned_by=None, description="", due_at=None, priority="medium", payload=None):
        task = StaffTask.objects.create(
            tenant=tenant,
            assignee=assignee,
            title=title,
            description=description,
            assigned_by=assigned_by,
            due_at=due_at,
            priority=priority,
            work_payload=payload or {},
        )
        self.repository.log_activity(assignee, "task_assigned", object_type="staff_task", object_id=str(task.id))
        self.event_service.publish("staff_task_assigned", {"task_id": str(task.id), "employee_id": str(assignee.id)}, tenant=tenant, user=assigned_by)
        return task

    def assign_kpi(self, *, tenant, employee, key, name, target_value, period, weight=100):
        return StaffKPI.objects.update_or_create(
            tenant=tenant,
            employee=employee,
            key=key,
            period=period,
            defaults={"name": name, "target_value": target_value, "weight": weight},
        )[0]

    def setup_default_permissions(self, tenant):
        role, _ = EnterpriseRole.objects.get_or_create(tenant=tenant, key="workforce-admin", defaults={"name": "Workforce Admin", "is_system": True})
        for key, label in (
            ("workforce.manage", "Manage Workforce"),
            ("workforce.attendance.manage", "Manage Attendance"),
            ("workforce.payroll.view", "View Payroll"),
            ("workforce.portal.access", "Employee Portal Access"),
        ):
            permission, _ = EnterprisePermission.objects.get_or_create(tenant=tenant, key=key, defaults={"label": label, "scope": "action"})
            RolePermission.objects.get_or_create(role=role, permission=permission, defaults={"allowed": True})
        return role

