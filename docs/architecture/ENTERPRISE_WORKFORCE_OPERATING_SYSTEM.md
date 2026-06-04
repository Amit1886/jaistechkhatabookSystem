# Enterprise Workforce Operating System

EWOS is an additive platform module for managing internal and external workforce without breaking existing ERP modules.

## Backend Architecture

```text
Tenant / Company / Branch
  -> Department
  -> Team
  -> Designation
  -> EmployeeProfile
  -> Shift / ShiftAssignment
  -> AttendanceLog
  -> LeaveRequest
  -> StaffTask
  -> StaffKPI
  -> Devices / Sessions / Documents / Activity
  -> Announcements / Discussions
```

API base:

`/api/v1/platform/workforce/`

Important endpoints:

- `dashboard/`
- `org-tree/`
- `self/attendance/`
- `employees/`
- `departments/`
- `teams/`
- `shifts/`
- `attendance/`
- `leave-requests/`
- `tasks/`
- `kpis/`
- `documents/`
- `announcements/`
- `discussions/`

## Organization Hierarchy

```text
Company
  -> Branch
  -> Department
  -> Team
  -> Manager
  -> Employee / Remote / Freelancer / Contractor / Gig / Delivery / Field / Consultant / Agency
```

Matrix reporting is supported through `EmployeeProfile.matrix_managers`.

## Lifecycle

Supported statuses:

- hiring
- onboarding
- probation
- active
- training
- notice
- exited

## Attendance And Shift

Attendance supports:

- biometric
- GPS
- selfie
- QR
- manual

Shift rules support grace minutes, overtime threshold, rotational shift rules, late penalty calculation, and device fingerprint capture.

## Self-Service Portal

Frontend components:

- `WorkforceDashboard`
- `OrgTree`
- `EmployeePortal`

Employees can mark attendance, view assigned work, initiate leave, view salary/payslip areas, and receive notifications through the unified UI system.

## Permissions

EWOS integrates with the enterprise identity permission engine:

- `workforce.manage`
- `workforce.attendance.manage`
- `workforce.payroll.view`
- `workforce.portal.access`

Strict screen/field/device/IP/working-hour restrictions should be configured through `platform_identity` permissions and middleware.

## Realtime

WebSocket path:

`/ws/platform/workforce/events/`

Event examples:

- `employee_created`
- `employee_lifecycle_changed`
- `attendance_marked`
- `leave_requested`
- `leave_decided`
- `staff_task_assigned`

