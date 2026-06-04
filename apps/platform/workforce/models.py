import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.platform.identity.models import Branch, Company, Tenant


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PublicWorkforceApplication(TimestampedModel):
    class ApplicantType(models.TextChoices):
        EMPLOYEE = "employee", "Employee"
        REMOTE = "remote", "Remote Worker"
        FREELANCER = "freelancer", "Freelancer"
        PART_TIME = "part_time", "Part-time Worker"
        DELIVERY = "delivery", "Delivery Partner"
        FIELD = "field", "Field Agent"
        PARTNER = "partner", "Partner"
        FRANCHISE = "franchise", "Franchise"
        RESELLER = "reseller", "Reseller"
        AGENCY = "agency", "Agency"

    class Status(models.TextChoices):
        NEW = "new", "New"
        SCREENING = "screening", "Screening"
        INTERVIEW = "interview", "Interview"
        SELECTED = "selected", "Selected"
        REJECTED = "rejected", "Rejected"
        ONBOARDED = "onboarded", "Onboarded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant_type = models.CharField(max_length=30, choices=ApplicantType.choices, db_index=True)
    full_name = models.CharField(max_length=180)
    mobile = models.CharField(max_length=30, db_index=True)
    email = models.EmailField(blank=True, default="", db_index=True)
    city = models.CharField(max_length=120, blank=True, default="", db_index=True)
    role_interest = models.CharField(max_length=180, blank=True, default="")
    experience_years = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    skills = models.TextField(blank=True, default="")
    resume = models.FileField(upload_to="workforce/applications/resumes/", null=True, blank=True)
    interview_slot = models.CharField(max_length=120, blank=True, default="")
    portfolio_url = models.URLField(blank=True, default="")
    referral_code = models.CharField(max_length=80, blank=True, default="", db_index=True)
    source = models.CharField(max_length=80, blank=True, default="landing", db_index=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.NEW, db_index=True)
    notes = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_public_applications"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["applicant_type", "status", "created_at"]),
            models.Index(fields=["mobile", "created_at"]),
        ]

    def __str__(self):
        return f"{self.full_name} - {self.applicant_type}"


class TenantScopedModel(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="%(class)s_records")
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True


class Department(TenantScopedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="workforce_departments")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="workforce_departments")
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    key = models.SlugField(max_length=140, db_index=True)
    name = models.CharField(max_length=180)
    cost_center = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        db_table = "workforce_departments"
        unique_together = ("tenant", "key")
        ordering = ("name",)

    def __str__(self):
        return self.name


class Designation(TenantScopedModel):
    key = models.SlugField(max_length=140, db_index=True)
    title = models.CharField(max_length=180)
    level = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "workforce_designations"
        unique_together = ("tenant", "key")
        ordering = ("level", "title")


class Team(TenantScopedModel):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="teams")
    key = models.SlugField(max_length=140, db_index=True)
    name = models.CharField(max_length=180)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_workforce_teams")
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="workforce_teams")

    class Meta:
        db_table = "workforce_teams"
        unique_together = ("tenant", "key")


class EmployeeProfile(TenantScopedModel):
    class WorkerType(models.TextChoices):
        EMPLOYEE = "employee", "Employee"
        REMOTE = "remote", "Remote Worker"
        FREELANCER = "freelancer", "Freelancer"
        CONTRACTOR = "contractor", "Contractor"
        GIG = "gig", "Gig Worker"
        DELIVERY = "delivery", "Delivery Staff"
        FIELD = "field", "Field Staff"
        CONSULTANT = "consultant", "Consultant"
        AGENCY = "agency", "Agency"

    class LifecycleStatus(models.TextChoices):
        HIRING = "hiring", "Hiring"
        ONBOARDING = "onboarding", "Onboarding"
        PROBATION = "probation", "Probation"
        ACTIVE = "active", "Active"
        TRAINING = "training", "Training"
        NOTICE = "notice", "Notice"
        EXITED = "exited", "Exited"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workforce_profile")
    employee_code = models.CharField(max_length=80, db_index=True)
    worker_type = models.CharField(max_length=30, choices=WorkerType.choices, default=WorkerType.EMPLOYEE, db_index=True)
    lifecycle_status = models.CharField(max_length=30, choices=LifecycleStatus.choices, default=LifecycleStatus.ONBOARDING, db_index=True)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name="employee_profiles")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="employee_profiles")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")
    reporting_manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="direct_reports")
    matrix_managers = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="matrix_reports")
    joining_date = models.DateField(null=True, blank=True)
    probation_end_date = models.DateField(null=True, blank=True)
    exit_date = models.DateField(null=True, blank=True)
    salary_structure = models.JSONField(default=dict, blank=True)
    incentive_model = models.JSONField(default=dict, blank=True)
    permission_profile = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_employees"
        unique_together = ("tenant", "employee_code")
        indexes = [models.Index(fields=["tenant", "worker_type", "lifecycle_status"])]

    def __str__(self):
        return self.employee_code


class Shift(TenantScopedModel):
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=80, db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    grace_minutes = models.PositiveIntegerField(default=0)
    overtime_after_minutes = models.PositiveIntegerField(default=0)
    rotational_rules = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_shifts"
        unique_together = ("tenant", "code")


class ShiftAssignment(TenantScopedModel):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="shift_assignments")
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name="assignments")
    starts_at = models.DateField()
    ends_at = models.DateField(null=True, blank=True)
    rules = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_shift_assignments"
        indexes = [models.Index(fields=["tenant", "employee", "starts_at"])]


class AttendanceLog(TenantScopedModel):
    class Method(models.TextChoices):
        BIOMETRIC = "biometric", "Biometric"
        GPS = "gps", "GPS"
        SELFIE = "selfie", "Selfie"
        QR = "qr", "QR"
        MANUAL = "manual", "Manual"

    class LogType(models.TextChoices):
        IN = "in", "In"
        OUT = "out", "Out"

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="attendance_logs")
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_logs")
    log_type = models.CharField(max_length=10, choices=LogType.choices, db_index=True)
    method = models.CharField(max_length=20, choices=Method.choices, db_index=True)
    logged_at = models.DateTimeField(default=timezone.now, db_index=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    selfie = models.ImageField(upload_to="workforce/selfies/", null=True, blank=True)
    device_fingerprint = models.CharField(max_length=220, blank=True, default="", db_index=True)
    verification_status = models.CharField(max_length=40, default="pending", db_index=True)
    penalty_minutes = models.PositiveIntegerField(default=0)
    overtime_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "workforce_attendance_logs"
        ordering = ("-logged_at",)


class LeaveRequest(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Review"
        APPROVAL = "approval", "Approval"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=80, db_index=True)
    starts_on = models.DateField()
    ends_on = models.DateField()
    reason = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="leave_approvals")
    decision_note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "workforce_leave_requests"
        ordering = ("-created_at",)


class StaffTask(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Review"
        APPROVAL = "approval", "Approval"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    assignee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="tasks")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_staff_tasks")
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    priority = models.CharField(max_length=20, default="medium", db_index=True)
    work_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_staff_tasks"
        ordering = ("status", "due_at", "-created_at")


class StaffKPI(TenantScopedModel):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="kpis")
    key = models.SlugField(max_length=140, db_index=True)
    name = models.CharField(max_length=180)
    target_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    current_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    period = models.CharField(max_length=30, db_index=True)
    weight = models.PositiveIntegerField(default=100)

    class Meta:
        db_table = "workforce_staff_kpis"
        unique_together = ("tenant", "employee", "key", "period")


class EmployeeDevice(TenantScopedModel):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="devices")
    fingerprint = models.CharField(max_length=220, db_index=True)
    name = models.CharField(max_length=180, blank=True, default="")
    status = models.CharField(max_length=30, default="pending", db_index=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "workforce_employee_devices"
        unique_together = ("tenant", "employee", "fingerprint")


class EmployeeSession(TenantScopedModel):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="sessions")
    session_key = models.CharField(max_length=120, db_index=True)
    device = models.ForeignKey(EmployeeDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions")
    started_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "workforce_employee_sessions"


class EmployeeDocument(TenantScopedModel):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=80, db_index=True)
    title = models.CharField(max_length=180)
    file = models.FileField(upload_to="workforce/documents/")
    verification_status = models.CharField(max_length=40, default="pending", db_index=True)
    expires_on = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "workforce_employee_documents"


class EmployeeActivityLog(TenantScopedModel):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="activity_logs")
    action = models.CharField(max_length=120, db_index=True)
    object_type = models.CharField(max_length=120, blank=True, default="")
    object_id = models.CharField(max_length=120, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "workforce_employee_activity_logs"
        ordering = ("-recorded_at",)


class Announcement(TenantScopedModel):
    title = models.CharField(max_length=220)
    message = models.TextField()
    audience = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="workforce_announcements")
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workforce_announcements"


class StaffDiscussion(TenantScopedModel):
    class DiscussionType(models.TextChoices):
        CHAT = "chat", "Chat"
        DEPARTMENT = "department", "Department"
        TASK = "task", "Task"
        FEEDBACK = "feedback", "Feedback"
        COMPLAINT = "complaint", "Anonymous Complaint"

    discussion_type = models.CharField(max_length=30, choices=DiscussionType.choices, db_index=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="discussions")
    task = models.ForeignKey(StaffTask, on_delete=models.SET_NULL, null=True, blank=True, related_name="discussions")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="workforce_discussions")
    subject = models.CharField(max_length=220)
    is_anonymous = models.BooleanField(default=False)
    ai_summary = models.TextField(blank=True, default="")

    class Meta:
        db_table = "workforce_discussions"


class ProductivitySignal(TenantScopedModel):
    class SignalType(models.TextChoices):
        TASK = "task", "Task Completion"
        WORK_HOURS = "work_hours", "Active Work Hours"
        APP_USAGE = "app_usage", "App Usage"
        BROWSER_USAGE = "browser_usage", "Browser Usage"
        SCREENSHOT = "screenshot", "Screenshot"
        IDLE = "idle", "Idle Detection"
        CODING = "coding", "Coding Activity"
        SUPPORT = "support", "Support Response"
        SALES = "sales", "Sales Activity"
        RATING = "rating", "Customer Rating"

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="productivity_signals")
    signal_type = models.CharField(max_length=40, choices=SignalType.choices, db_index=True)
    source = models.CharField(max_length=120, blank=True, default="", db_index=True)
    score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    weight = models.PositiveIntegerField(default=100)
    duration_seconds = models.PositiveIntegerField(default=0)
    evidence = models.JSONField(default=dict, blank=True)
    captured_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "workforce_productivity_signals"
        indexes = [models.Index(fields=["tenant", "employee", "signal_type", "captured_at"])]


class EmployeeScoreSnapshot(TenantScopedModel):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="score_snapshots")
    period = models.CharField(max_length=30, db_index=True)
    productivity_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    discipline_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    trust_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    leadership_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    communication_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    quality_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    fraud_risk_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    performance_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_score_snapshots"
        unique_together = ("tenant", "employee", "period")


class PayrollPolicy(TenantScopedModel):
    class PayType(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        HOURLY = "hourly", "Hourly"
        TASK = "task", "Task Based"
        COMMISSION = "commission", "Commission"
        REVENUE_SHARE = "revenue_share", "Revenue Share"
        HYBRID = "hybrid", "Hybrid"

    name = models.CharField(max_length=180)
    pay_type = models.CharField(max_length=30, choices=PayType.choices, default=PayType.MONTHLY, db_index=True)
    base_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    hourly_rate = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    task_rate = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    commission_rules = models.JSONField(default=dict, blank=True)
    incentive_rules = models.JSONField(default=dict, blank=True)
    deduction_rules = models.JSONField(default=dict, blank=True)
    tax_rules = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_payroll_policies"


class EmployeePayrollProfile(TenantScopedModel):
    employee = models.OneToOneField(EmployeeProfile, on_delete=models.CASCADE, related_name="payroll_profile")
    policy = models.ForeignKey(PayrollPolicy, on_delete=models.SET_NULL, null=True, blank=True, related_name="employee_profiles")
    bank_name = models.CharField(max_length=160, blank=True, default="")
    account_number = models.CharField(max_length=60, blank=True, default="")
    ifsc = models.CharField(max_length=16, blank=True, default="")
    upi_id = models.CharField(max_length=120, blank=True, default="")
    reimbursement_rules = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_employee_payroll_profiles"


class PayrollRun(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Review"
        APPROVAL = "approval", "Approval"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    period = models.CharField(max_length=30, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="generated_payroll_runs")
    totals = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_payroll_runs"
        unique_together = ("tenant", "period")


class Payslip(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="payslips")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    gross_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    incentive_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    overtime_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    bonus_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reimbursement_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    deduction_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    penalty_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_items = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "workforce_payslips"
        unique_together = ("tenant", "payroll_run", "employee")


class PayoutInstruction(TenantScopedModel):
    class Method(models.TextChoices):
        UPI = "upi", "UPI"
        BANK = "bank", "Bank Transfer"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    payslip = models.OneToOneField(Payslip, on_delete=models.CASCADE, related_name="payout")
    method = models.CharField(max_length=20, choices=Method.choices, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    destination = models.JSONField(default=dict, blank=True)
    provider_reference = models.CharField(max_length=160, blank=True, default="")
    error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "workforce_payout_instructions"


class DisciplineCase(TenantScopedModel):
    class ViolationType(models.TextChoices):
        LATE = "late", "Late Attendance"
        IDLE_ABUSE = "idle_abuse", "Idle Abuse"
        FAKE_ATTENDANCE = "fake_attendance", "Fake Attendance"
        FAKE_PRODUCTIVITY = "fake_productivity", "Fake Productivity"
        POLICY = "policy", "Policy Violation"
        MISCONDUCT = "misconduct", "Misconduct"
        POOR_PERFORMANCE = "poor_performance", "Poor Performance"

    class Action(models.TextChoices):
        WARNING = "warning", "Warning"
        PENALTY = "penalty", "Penalty"
        SUSPENSION = "suspension", "Suspension"
        ESCALATION = "escalation", "Escalation"

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="discipline_cases")
    violation_type = models.CharField(max_length=40, choices=ViolationType.choices, db_index=True)
    action = models.CharField(max_length=30, choices=Action.choices, db_index=True)
    severity = models.CharField(max_length=20, default="medium", db_index=True)
    status = models.CharField(max_length=20, default="draft", db_index=True)
    description = models.TextField(blank=True, default="")
    evidence = models.JSONField(default=dict, blank=True)
    penalty_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    escalation_history = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "workforce_discipline_cases"


class FraudRiskSignal(TenantScopedModel):
    class RiskType(models.TextChoices):
        FAKE_SCREENSHOT = "fake_screenshot", "Fake Screenshot"
        FAKE_ATTENDANCE = "fake_attendance", "Fake Attendance"
        DUPLICATE_WORK = "duplicate_work", "Duplicate Work"
        AUTOMATION_ABUSE = "automation_abuse", "Automation Abuse"
        GPS_SPOOFING = "gps_spoofing", "GPS Spoofing"
        SUSPICIOUS_PATTERN = "suspicious_pattern", "Suspicious Work Pattern"
        FAKE_SUPPORT = "fake_support", "Fake Support Resolution"

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="fraud_risks")
    risk_type = models.CharField(max_length=50, choices=RiskType.choices, db_index=True)
    risk_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default="open", db_index=True)
    evidence = models.JSONField(default=dict, blank=True)
    detected_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "workforce_fraud_risk_signals"


class HRInsight(TenantScopedModel):
    class InsightType(models.TextChoices):
        RESIGNATION = "resignation", "Resignation Risk"
        BURNOUT = "burnout", "Burnout Risk"
        PROMOTION = "promotion", "Promotion Recommendation"
        TRAINING = "training", "Training Recommendation"
        STAFFING = "staffing", "Staffing Optimization"
        PAYROLL_COST = "payroll_cost", "Payroll Cost Optimization"

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, null=True, blank=True, related_name="hr_insights")
    insight_type = models.CharField(max_length=40, choices=InsightType.choices, db_index=True)
    confidence = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    title = models.CharField(max_length=220)
    recommendation = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, default="open", db_index=True)

    class Meta:
        db_table = "workforce_hr_insights"


class WorkforceProfitabilitySnapshot(TenantScopedModel):
    period = models.CharField(max_length=30, db_index=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="profitability_snapshots")
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="profitability_snapshots")
    revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payroll_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    support_efficiency = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    sales_efficiency = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    roi = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_profitability_snapshots"
        indexes = [models.Index(fields=["tenant", "period"])]


class RemoteWorkSession(TenantScopedModel):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="remote_work_sessions")
    project_key = models.CharField(max_length=140, blank=True, default="", db_index=True)
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    active_seconds = models.PositiveIntegerField(default=0)
    idle_seconds = models.PositiveIntegerField(default=0)
    webcam_verified = models.BooleanField(default=False, db_index=True)
    activity_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    authenticity_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    contribution_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_remote_work_sessions"
        ordering = ("-started_at",)


class RemoteActivityEvent(TenantScopedModel):
    class EventType(models.TextChoices):
        APP = "app", "App Usage"
        BROWSER = "browser", "Browser Usage"
        SCREENSHOT = "screenshot", "Screenshot"
        WEBCAM = "webcam", "Webcam Verification"
        KEYBOARD = "keyboard", "Keyboard Activity"
        MOUSE = "mouse", "Mouse Activity"
        COMMIT = "commit", "Code Commit"
        TASK_UPDATE = "task_update", "Task Update"

    session = models.ForeignKey(RemoteWorkSession, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=30, choices=EventType.choices, db_index=True)
    captured_at = models.DateTimeField(default=timezone.now, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    risk_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        db_table = "workforce_remote_activity_events"


class GigTask(TenantScopedModel):
    class GigType(models.TextChoices):
        MICRO = "micro", "Micro Task"
        SUPPORT = "support", "Support Gig"
        PROJECT = "project", "Project Gig"
        DELIVERY = "delivery", "Delivery Job"
        MARKETING = "marketing", "Marketing Task"
        SALES = "sales", "Sales Campaign"
        FIELD = "field", "Field Operation"
        FREELANCE = "freelance", "Freelance Assignment"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", "In Progress"
        REVIEW = "review", "Review"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    title = models.CharField(max_length=220)
    gig_type = models.CharField(max_length=30, choices=GigType.choices, db_index=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN, db_index=True)
    required_skills = models.JSONField(default=list, blank=True)
    payout_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    priority = models.CharField(max_length=20, default="medium", db_index=True)
    location = models.JSONField(default=dict, blank=True)
    deadline_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="posted_gig_tasks")
    assignee = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="gig_tasks")
    assignment_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        db_table = "workforce_gig_tasks"
        ordering = ("status", "priority", "deadline_at")


class MarketplaceListing(TenantScopedModel):
    class ListingType(models.TextChoices):
        JOB = "job", "Job"
        PROJECT = "project", "Project"
        FRANCHISE = "franchise", "Franchise"
        RESELLER = "reseller", "Reseller"
        SUPPORT_VENDOR = "support_vendor", "Support Vendor"

    title = models.CharField(max_length=220)
    listing_type = models.CharField(max_length=40, choices=ListingType.choices, db_index=True)
    description = models.TextField(blank=True, default="")
    budget_min = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    budget_max = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    requirements = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=30, default="open", db_index=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="marketplace_listings")

    class Meta:
        db_table = "workforce_marketplace_listings"


class MarketplaceApplication(TenantScopedModel):
    listing = models.ForeignKey(MarketplaceListing, on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="marketplace_applications")
    agency_name = models.CharField(max_length=180, blank=True, default="")
    proposal = models.TextField(blank=True, default="")
    quoted_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=30, default="submitted", db_index=True)

    class Meta:
        db_table = "workforce_marketplace_applications"


class PartnerProfile(TenantScopedModel):
    class PartnerType(models.TextChoices):
        FRANCHISE = "franchise", "Franchise"
        RESELLER = "reseller", "Reseller"
        SUPPORT = "support", "Support Partner"
        AGENCY = "agency", "Agency"
        BPO = "bpo", "BPO"
        DELIVERY = "delivery", "Delivery Partner"

    name = models.CharField(max_length=180)
    partner_type = models.CharField(max_length=30, choices=PartnerType.choices, db_index=True)
    owner = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_partner_profiles")
    territory = models.JSONField(default=dict, blank=True)
    white_label_config = models.JSONField(default=dict, blank=True)
    commission_rules = models.JSONField(default=dict, blank=True)
    revenue_share_rules = models.JSONField(default=dict, blank=True)
    onboarding_status = models.CharField(max_length=30, default="draft", db_index=True)

    class Meta:
        db_table = "workforce_partner_profiles"


class PartnerSettlement(TenantScopedModel):
    partner = models.ForeignKey(PartnerProfile, on_delete=models.CASCADE, related_name="settlements")
    period = models.CharField(max_length=30, db_index=True)
    revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    commission = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    revenue_share = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payable = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=30, default="draft", db_index=True)

    class Meta:
        db_table = "workforce_partner_settlements"


class TrainingCourse(TenantScopedModel):
    title = models.CharField(max_length=220)
    category = models.CharField(max_length=120, db_index=True)
    description = models.TextField(blank=True, default="")
    content = models.JSONField(default=dict, blank=True)
    ai_assistant_prompt = models.TextField(blank=True, default="")
    passing_score = models.DecimalField(max_digits=8, decimal_places=2, default=70)

    class Meta:
        db_table = "workforce_training_courses"


class Certification(TenantScopedModel):
    course = models.ForeignKey(TrainingCourse, on_delete=models.CASCADE, related_name="certifications")
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="certifications")
    score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    status = models.CharField(max_length=30, default="in_progress", db_index=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    analytics = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_certifications"
        unique_together = ("tenant", "course", "employee")


class EmployeeWallet(TenantScopedModel):
    employee = models.OneToOneField(EmployeeProfile, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    bonus_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reward_points = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "workforce_employee_wallets"


class WalletTransaction(TenantScopedModel):
    wallet = models.ForeignKey(EmployeeWallet, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=40, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    points = models.IntegerField(default=0)
    source_type = models.CharField(max_length=120, blank=True, default="")
    source_id = models.CharField(max_length=120, blank=True, default="")
    note = models.CharField(max_length=240, blank=True, default="")

    class Meta:
        db_table = "workforce_wallet_transactions"


class BusinessNetworkNode(TenantScopedModel):
    class NodeType(models.TextChoices):
        COMPANY = "company", "Company"
        FRANCHISE = "franchise", "Franchise"
        BPO = "bpo", "BPO"
        RESELLER = "reseller", "Reseller"
        OUTSOURCING = "outsourcing", "Outsourcing"
        WHITE_LABEL = "white_label", "White Label Deployment"

    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    node_type = models.CharField(max_length=40, choices=NodeType.choices, db_index=True)
    name = models.CharField(max_length=180)
    linked_tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="network_nodes")
    operating_rules = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_business_network_nodes"


class CognitiveEmployeeProfile(TenantScopedModel):
    employee = models.OneToOneField(EmployeeProfile, on_delete=models.CASCADE, related_name="cognitive_profile")
    skills = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)
    behavioral_analytics = models.JSONField(default=dict, blank=True)
    productivity_history = models.JSONField(default=dict, blank=True)
    attendance_history = models.JSONField(default=dict, blank=True)
    trust_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    leadership_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    engagement_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    morale_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    burnout_risk = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    resignation_probability = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    promotion_probability = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    ai_career_insights = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_cognitive_employee_profiles"


class BehavioralSignal(TenantScopedModel):
    class SignalType(models.TextChoices):
        ENGAGEMENT = "engagement", "Engagement"
        STRESS = "stress", "Stress"
        COLLABORATION = "collaboration", "Collaboration"
        MORALE = "morale", "Morale"
        COMMUNICATION = "communication", "Communication"
        BURNOUT = "burnout", "Burnout"
        RESIGNATION = "resignation", "Resignation"

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="behavioral_signals")
    signal_type = models.CharField(max_length=40, choices=SignalType.choices, db_index=True)
    score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    confidence = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    source = models.CharField(max_length=120, blank=True, default="", db_index=True)
    evidence = models.JSONField(default=dict, blank=True)
    captured_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "workforce_behavioral_signals"
        indexes = [models.Index(fields=["tenant", "employee", "signal_type", "captured_at"])]


class EmployeeTransparencyRecord(TenantScopedModel):
    class RecordType(models.TextChoices):
        SALARY = "salary", "Salary Calculation"
        INCENTIVE = "incentive", "Incentive Calculation"
        KPI = "kpi", "KPI Calculation"
        ATTENDANCE = "attendance", "Attendance Record"
        DISCIPLINE = "discipline", "Disciplinary History"
        PROMOTION = "promotion", "Promotion Eligibility"
        PERFORMANCE = "performance", "Performance Analytics"

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="transparency_records")
    record_type = models.CharField(max_length=40, choices=RecordType.choices, db_index=True)
    period = models.CharField(max_length=30, blank=True, default="", db_index=True)
    title = models.CharField(max_length=220)
    calculation = models.JSONField(default=dict, blank=True)
    visible_to_employee = models.BooleanField(default=True, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workforce_employee_transparency_records"
        indexes = [models.Index(fields=["tenant", "employee", "record_type", "period"])]


class CultureEngagementProgram(TenantScopedModel):
    class ProgramType(models.TextChoices):
        RECOGNITION = "recognition", "Recognition"
        REWARD = "reward", "Reward"
        LEADERBOARD = "leaderboard", "Leaderboard"
        WELLNESS = "wellness", "Wellness"
        SURVEY = "survey", "Survey"

    title = models.CharField(max_length=220)
    program_type = models.CharField(max_length=40, choices=ProgramType.choices, db_index=True)
    rules = models.JSONField(default=dict, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workforce_culture_engagement_programs"


class EmployeeRecognition(TenantScopedModel):
    program = models.ForeignKey(CultureEngagementProgram, on_delete=models.SET_NULL, null=True, blank=True, related_name="recognitions")
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="recognitions")
    given_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="given_recognitions")
    title = models.CharField(max_length=220)
    points = models.PositiveIntegerField(default=0)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_employee_recognitions"


class CareerGrowthPlan(TenantScopedModel):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="career_growth_plans")
    target_role = models.CharField(max_length=180)
    learning_path = models.JSONField(default=list, blank=True)
    recommended_certifications = models.JSONField(default=list, blank=True)
    promotion_readiness = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    leadership_potential = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    ai_recommendation = models.TextField(blank=True, default="")
    status = models.CharField(max_length=30, default="draft", db_index=True)

    class Meta:
        db_table = "workforce_career_growth_plans"


class HRComplianceLedger(TenantScopedModel):
    class LedgerType(models.TextChoices):
        HR_LOG = "hr_log", "HR Log"
        LEGAL_DOCUMENT = "legal_document", "Legal Document"
        ATTENDANCE_AUDIT = "attendance_audit", "Attendance Audit"
        PAYROLL_COMPLIANCE = "payroll_compliance", "Payroll Compliance"
        LABOR_LAW = "labor_law", "Labor Law"
        DISCIPLINE_AUDIT = "discipline_audit", "Discipline Audit"

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="compliance_ledgers")
    ledger_type = models.CharField(max_length=50, choices=LedgerType.choices, db_index=True)
    title = models.CharField(max_length=220)
    payload = models.JSONField(default=dict, blank=True)
    immutable_hash = models.CharField(max_length=128, blank=True, default="", db_index=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hr_compliance_records")

    class Meta:
        db_table = "workforce_hr_compliance_ledgers"
        indexes = [models.Index(fields=["tenant", "ledger_type", "created_at"])]


class OrganizationalGraphNode(TenantScopedModel):
    node_type = models.CharField(max_length=60, db_index=True)
    object_id = models.CharField(max_length=120, db_index=True)
    label = models.CharField(max_length=220)
    metrics = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_org_graph_nodes"
        unique_together = ("tenant", "node_type", "object_id")


class OrganizationalGraphEdge(TenantScopedModel):
    source = models.ForeignKey(OrganizationalGraphNode, on_delete=models.CASCADE, related_name="outgoing_edges")
    target = models.ForeignKey(OrganizationalGraphNode, on_delete=models.CASCADE, related_name="incoming_edges")
    relation_type = models.CharField(max_length=80, db_index=True)
    weight = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    metrics = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_org_graph_edges"
        indexes = [models.Index(fields=["tenant", "relation_type"])]


class EnterpriseCopilotSession(TenantScopedModel):
    class CopilotType(models.TextChoices):
        HR = "hr", "HR Assistant"
        PAYROLL = "payroll", "Payroll Assistant"
        ATTENDANCE = "attendance", "Attendance Assistant"
        COACH = "coach", "Employee Coach"
        REPORTING = "reporting", "Reporting Assistant"
        MANAGEMENT = "management", "Management Workflow"

    copilot_type = models.CharField(max_length=40, choices=CopilotType.choices, db_index=True)
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="copilot_sessions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="workforce_copilot_sessions")
    prompt = models.TextField()
    response = models.TextField(blank=True, default="")
    context = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=30, default="open", db_index=True)

    class Meta:
        db_table = "workforce_enterprise_copilot_sessions"


class SelfHealingGovernanceIncident(TenantScopedModel):
    class IncidentType(models.TextChoices):
        PAYROLL = "payroll", "Payroll Inconsistency"
        PRODUCTIVITY = "productivity", "Productivity Drop"
        ATTENDANCE = "attendance", "Attendance Anomaly"
        IMBALANCE = "imbalance", "Workforce Imbalance"
        HR_RISK = "hr_risk", "HR Risk"
        BURNOUT = "burnout", "Burnout Risk"
        FRAUD = "fraud", "Fraud Risk"

    incident_type = models.CharField(max_length=50, choices=IncidentType.choices, db_index=True)
    severity = models.CharField(max_length=20, default="medium", db_index=True)
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="governance_incidents")
    title = models.CharField(max_length=220)
    detection_payload = models.JSONField(default=dict, blank=True)
    triggered_workflow = models.CharField(max_length=140, blank=True, default="")
    status = models.CharField(max_length=30, default="open", db_index=True)

    class Meta:
        db_table = "workforce_self_healing_governance_incidents"
        indexes = [models.Index(fields=["tenant", "incident_type", "status"])]


class CognitiveCommandCenterSnapshot(TenantScopedModel):
    period = models.CharField(max_length=30, db_index=True)
    workforce_health = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    engagement_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    culture_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    payroll_accuracy = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    operational_efficiency = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    profitability_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    ai_insights = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "workforce_cognitive_command_center_snapshots"
        unique_together = ("tenant", "period")


class WorkToolDefinition(TenantScopedModel):
    class ToolCategory(models.TextChoices):
        SUPPORT = "support", "Support"
        SALES = "sales", "Sales"
        HR = "hr", "HR"
        ACCOUNTING = "accounting", "Accounting"
        MARKETING = "marketing", "Marketing"
        REMOTE = "remote", "Remote Workforce"
        FIELD = "field", "Field and Delivery"
        GIG = "gig", "Gig Worker"
        PROJECT = "project", "Project"
        REPORTING = "reporting", "Reporting"
        HARDWARE = "hardware", "Hardware"

    key = models.SlugField(max_length=140, db_index=True)
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=40, choices=ToolCategory.choices, db_index=True)
    icon = models.CharField(max_length=80, blank=True, default="")
    route = models.CharField(max_length=220, blank=True, default="")
    required_permissions = models.JSONField(default=list, blank=True)
    role_rules = models.JSONField(default=dict, blank=True)
    config_schema = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_work_tool_definitions"
        unique_together = ("tenant", "key")


class EmployeeToolAssignment(TenantScopedModel):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="tool_assignments")
    tool = models.ForeignKey(WorkToolDefinition, on_delete=models.CASCADE, related_name="employee_assignments")
    source = models.CharField(max_length=40, default="rule", db_index=True)
    enabled = models.BooleanField(default=True, db_index=True)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_employee_tool_assignments"
        unique_together = ("tenant", "employee", "tool")


class UnifiedDashboardConfig(TenantScopedModel):
    key = models.SlugField(max_length=140, db_index=True)
    title = models.CharField(max_length=180)
    audience = models.JSONField(default=dict, blank=True)
    widgets = models.JSONField(default=list, blank=True)
    layout = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_unified_dashboard_configs"
        unique_together = ("tenant", "key")


class WorkProject(TenantScopedModel):
    name = models.CharField(max_length=220)
    project_type = models.CharField(max_length=60, default="internal", db_index=True)
    owner = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_work_projects")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_projects")
    status = models.CharField(max_length=30, default="active", db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_work_projects"


class WorkBoard(TenantScopedModel):
    project = models.ForeignKey(WorkProject, on_delete=models.CASCADE, related_name="boards")
    name = models.CharField(max_length=180)
    board_type = models.CharField(max_length=40, default="kanban", db_index=True)
    columns = models.JSONField(default=list, blank=True)
    automation_rules = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "workforce_work_boards"


class WorkItem(TenantScopedModel):
    class WorkType(models.TextChoices):
        TASK = "task", "Task"
        TICKET = "ticket", "Ticket"
        BUG = "bug", "Bug"
        LEAD = "lead", "Lead"
        APPROVAL = "approval", "Approval"
        DELIVERY = "delivery", "Delivery"
        MARKETING = "marketing", "Marketing"
        FINANCE = "finance", "Finance"

    project = models.ForeignKey(WorkProject, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_items")
    board = models.ForeignKey(WorkBoard, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_items")
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="subtasks")
    work_type = models.CharField(max_length=40, choices=WorkType.choices, db_index=True)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=40, default="draft", db_index=True)
    priority = models.CharField(max_length=20, default="medium", db_index=True)
    assignee = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="execution_work_items")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reported_work_items")
    due_at = models.DateTimeField(null=True, blank=True)
    sla_due_at = models.DateTimeField(null=True, blank=True)
    estimate_minutes = models.PositiveIntegerField(default=0)
    actual_minutes = models.PositiveIntegerField(default=0)
    source_type = models.CharField(max_length=120, blank=True, default="", db_index=True)
    source_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_execution_work_items"
        indexes = [
            models.Index(fields=["tenant", "assignee", "status"]),
            models.Index(fields=["tenant", "work_type", "status"]),
        ]


class WorkComment(TenantScopedModel):
    work_item = models.ForeignKey(WorkItem, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_comments")
    message = models.TextField()
    visibility = models.CharField(max_length=30, default="team", db_index=True)

    class Meta:
        db_table = "workforce_work_comments"


class WorkAttachment(TenantScopedModel):
    work_item = models.ForeignKey(WorkItem, on_delete=models.CASCADE, related_name="attachments")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_attachments")
    title = models.CharField(max_length=180)
    file = models.FileField(upload_to="workforce/execution/attachments/", null=True, blank=True)
    external_url = models.URLField(blank=True, default="")

    class Meta:
        db_table = "workforce_work_attachments"


class TeamChannel(TenantScopedModel):
    name = models.CharField(max_length=180)
    channel_type = models.CharField(max_length=40, default="team", db_index=True)
    project = models.ForeignKey(WorkProject, on_delete=models.SET_NULL, null=True, blank=True, related_name="channels")
    members = models.ManyToManyField(EmployeeProfile, blank=True, related_name="team_channels")
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_team_channels"


class TeamMessage(TenantScopedModel):
    channel = models.ForeignKey(TeamChannel, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="team_messages")
    message = models.TextField()
    message_type = models.CharField(max_length=40, default="text", db_index=True)
    ai_summary = models.TextField(blank=True, default="")

    class Meta:
        db_table = "workforce_team_messages"


class WorkActivityRecord(TenantScopedModel):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="execution_activity_records")
    work_item = models.ForeignKey(WorkItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="activity_records")
    activity_type = models.CharField(max_length=80, db_index=True)
    source = models.CharField(max_length=80, blank=True, default="", db_index=True)
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    quality_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    productivity_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    fraud_risk_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    evidence = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_work_activity_records"
        indexes = [models.Index(fields=["tenant", "employee", "activity_type", "started_at"])]


class UniversalHardwareDevice(TenantScopedModel):
    class DeviceType(models.TextChoices):
        DESKTOP = "desktop", "Desktop"
        MOBILE = "mobile", "Mobile"
        TABLET = "tablet", "Tablet"
        POS = "pos", "POS"
        BARCODE = "barcode", "Barcode Scanner"
        BIOMETRIC = "biometric", "Biometric"
        PRINTER = "printer", "Thermal Printer"
        QR = "qr", "QR Scanner"
        WEBCAM = "webcam", "Webcam"
        GPS = "gps", "GPS Device"
        KIOSK = "kiosk", "Kiosk"

    device_type = models.CharField(max_length=40, choices=DeviceType.choices, db_index=True)
    name = models.CharField(max_length=180)
    fingerprint = models.CharField(max_length=220, blank=True, default="", db_index=True)
    assigned_employee = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="universal_devices")
    status = models.CharField(max_length=30, default="active", db_index=True)
    capabilities = models.JSONField(default=list, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workforce_universal_hardware_devices"


class ExecutionCommandSnapshot(TenantScopedModel):
    period = models.CharField(max_length=30, db_index=True)
    live_employees = models.PositiveIntegerField(default=0)
    active_work_items = models.PositiveIntegerField(default=0)
    support_tickets = models.PositiveIntegerField(default=0)
    sales_activities = models.PositiveIntegerField(default=0)
    remote_sessions = models.PositiveIntegerField(default=0)
    field_locations = models.PositiveIntegerField(default=0)
    payroll_projection = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    ai_alerts = models.PositiveIntegerField(default=0)
    workload_balance_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_execution_command_snapshots"
        unique_together = ("tenant", "period")
