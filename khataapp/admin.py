# khataapp/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.http import FileResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from .models import (
    Party, Transaction, ReportSchedule,
    CompanySettings, UserProfile,
    CreditSettings, CreditAccount, CreditEntry,
    EMI, Penalty, ContactMessage,
    LoginLink, ReminderLog, FieldAgent, CollectorVisit,
    OfflineMessage, SupplierPayment, StockLedger
)

from .utils.credit_report import (
    generate_credit_report_pdf,
    generate_credit_report_pdf_for_party
)

# Central Business Engine (admin visibility)
from solo.admin import SingletonModelAdmin
from khataapp.core_engine.models.engine import BusinessGrowthEngine
from khataapp.core_engine.models.logs import EngineEventLog, RewardLedgerEntry
from khataapp.core_engine.models.loyalty import LoyaltyAccount, LoyaltyLedgerEntry
from khataapp.core_engine.models.referral import ReferralRecord
from khataapp.core_engine.models.settings import EngineControlPanelSettings
from khataapp.core_engine.models.tasks import DailyTaskCompletion, DailyTaskDefinition

# ====
# PARTY
# ====

@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'mobile', 'party_type', 'email', 'is_premium',
        'created_at', 'credit_grade_badge', 'balance_display',
        'whatsapp_status', 'sms_status',
        'payment_link_display', 'download_report_button', 'login_link_button'
    )

    list_filter = ('party_type', 'is_premium', 'credit_grade')
    search_fields = ('name', 'mobile', 'upi_id', 'whatsapp_number', 'sms_number')
    readonly_fields = ('payment_link_display', 'balance_display', 'login_link_preview')
    actions = ['download_credit_report', 'generate_whatsapp_login_link']

    def balance_display(self, obj):
        return f"₹{obj.total_credit() - obj.total_debit()}"
    balance_display.short_description = "Balance"

    def whatsapp_status(self, obj):
        return "✅ Active" if obj.whatsapp_number else "❌ No WhatsApp"

    def sms_status(self, obj):
        return "✅ Active" if obj.sms_number else "❌ No SMS"

    def payment_link_display(self, obj):
        link = obj.get_payment_link()
        if link:
            return format_html('<a href="{}" target="_blank">Pay Now</a>', link)
        return "-"

    def credit_grade_badge(self, obj):
        colors = {
            'A+': '#0ea5e9',
            'A': '#16a34a',
            'B': '#22c55e',
            'C': '#f59e0b',
            'D': '#ef4444',
            '-': '#6b7280',
        }
        grade = obj.credit_grade or '-'
        return format_html(
            '<span style="padding:2px 8px;border-radius:12px;color:white;background:{};">{}</span>',
            colors.get(grade, '#6b7280'), grade
        )
    credit_grade_badge.short_description = "Credit Grade"

    def download_credit_report(self, request, queryset):
        pdf = generate_credit_report_pdf()
        return FileResponse(pdf, as_attachment=True, filename="credit_report.pdf")

    def download_report_button(self, obj):
        return format_html(
            '<a class="button" href="{}">📄 PDF</a>',
            f"{obj.id}/download-report/"
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:party_id>/download-report/",
                self.admin_site.admin_view(self.download_report_view),
                name="party_download_report"
            ),
            path(
                "<int:party_id>/generate-login-link/",
                self.admin_site.admin_view(self.generate_login_link_view),
                name="party_generate_login_link"
            ),
        ]
        return custom_urls + urls

    def download_report_view(self, request, party_id):
        party = get_object_or_404(Party, id=party_id)
        pdf = generate_credit_report_pdf_for_party(party)
        return FileResponse(pdf, as_attachment=True, filename=f"{party.name}_credit_report.pdf")

    def _get_or_create_party_user(self, party):
        User = get_user_model()

        if party.mobile:
            user = User.objects.filter(mobile=party.mobile).first()
            if user:
                return user

        # Fallback unique email
        base_email = None
        if party.mobile:
            base_email = f"{party.mobile}@party.local"


        else:
            safe = slugify(party.name) or f"party{party.id}"
            base_email = f"{safe}.{party.id}@party.local"

        user = User.objects.filter(email__iexact=base_email).first()
        if user:
            return user

        return User.objects.create(
            username=party.name[:150],
            email=base_email,
            mobile=party.mobile,
            is_active=False,
            is_otp_verified=False
        )

    def _create_login_link_and_queue(self, request, party):
        mobile = party.whatsapp_number or party.mobile
        if not mobile:
            return None, "missing_mobile"

        user = self._get_or_create_party_user(party)
        active = LoginLink.objects.filter(user=user, purpose="dashboard", is_active=True).first()
        if active:
            link = active
        else:
            expires_at = timezone.now() + timedelta(days=7)
            link = LoginLink.objects.create(
                user=user,
                purpose="dashboard",
                expires_at=expires_at
            )

        url = request.build_absolute_uri(
            reverse("accounts:login_link", args=[link.token])
        )
        message = f"Click here for more details \uD83D\uDC49 {url}"

        OfflineMessage.objects.create(
            party=party,
            message=message,
            channel="whatsapp",
            status="pending"
        )
        return link, None

    def generate_whatsapp_login_link(self, request, queryset):
        created = 0
        skipped = 0
        for party in queryset:
            link, error = self._create_login_link_and_queue(request, party)
            if error == "missing_mobile":
                skipped += 1
                continue
            if link:
                created += 1

        if created:
            self.message_user(request, f"Generated {created} WhatsApp login link(s).")
        if skipped:
            self.message_user(request, f"Skipped {skipped} party(s) without mobile/WhatsApp.", level="warning")

    generate_whatsapp_login_link.short_description = "Generate WhatsApp login link (queue)"

    def login_link_button(self, obj):
        return format_html(
            '<a class="button" href="{}">WhatsApp Link</a>',
            f"{obj.id}/generate-login-link/"
        )
    login_link_button.short_description = "Login Link"

    def login_link_preview(self, obj):
        user = self._get_or_create_party_user(obj)
        link = LoginLink.objects.filter(user=user, purpose="dashboard", is_active=True).first()
        if not link:
            return "No active login link yet."
        base_url = getattr(settings, "BASE_URL", "").rstrip("/")
        path = reverse("accounts:login_link", args=[link.token])
        url = f"{base_url}{path}" if base_url else path
        return f"Click here for more details 👉 {url}"
    login_link_preview.short_description = "WhatsApp Preview"

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if "login_link_preview" not in fields:
            fields.append("login_link_preview")
        return fields

    def generate_login_link_view(self, request, party_id):
        party = get_object_or_404(Party, id=party_id)
        link, error = self._create_login_link_and_queue(request, party)
        if error == "missing_mobile":
            self.message_user(request, "Party has no mobile/WhatsApp number.", level="warning")
        else:
            self.message_user(request, "WhatsApp login link queued.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


# ====
# REPORT SCHEDULE
# ====

@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ('send_date', 'send_time', 'is_active')
    list_filter = ('is_active',)


# ====
# TRANSACTION
# ====

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "party", "txn_type", "amount", "date",
        "receipt_link", "send_whatsapp_button", "send_sms_button"
    )

    list_filter = ("txn_type", "date")
    search_fields = ("party__name",)
    fields = ('party', 'txn_type', 'amount', 'notes', 'receipt')

    def receipt_link(self, obj):
        if obj.receipt:
            return format_html('<a href="{}" target="_blank">📎 View</a>', obj.receipt.url)
        return "-"

    def send_whatsapp_button(self, obj):
        return format_html(
            '<a class="button" href="send-whatsapp/{}/">📲 WhatsApp</a>', obj.id
        )

    def send_sms_button(self, obj):
        return format_html(
            '<a class="button" href="send-sms/{}/">📩 SMS</a>', obj.id
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'send-whatsapp/<int:txn_id>/',
                self.admin_site.admin_view(self.send_whatsapp),
                name='transaction_whatsapp'
            ),
            path(
                'send-sms/<int:txn_id>/',
                self.admin_site.admin_view(self.send_sms),
                name='transaction_sms'
            ),
        ]
        return custom_urls + urls

    def send_whatsapp(self, request, txn_id):
        # yahan API integration aayega
        self.message_user(request, "WhatsApp sent successfully")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    def send_sms(self, request, txn_id):
        self.message_user(request, "SMS sent successfully")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


# ====
# SETTINGS & USERS
# ====

@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'auto_sms_send', 'enable_auto_whatsapp', 'enable_monthly_email', 'whatsapp_number')
    list_editable = ('auto_sms_send', 'enable_auto_whatsapp', 'enable_monthly_email')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "business_name", "mobile", "created_from")
    list_filter = ("plan", "created_from")


# ====
# CREDIT MODULE
# ====

@admin.register(CreditSettings)
class CreditSettingsAdmin(admin.ModelAdmin):
    list_display = ("interest_rate", "penalty_rate_percent", "apply_after_days", "allow_partial_payment")


@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    list_display = ("party", "credit_limit", "outstanding", "updated_at")


@admin.register(CreditEntry)
class CreditEntryAdmin(admin.ModelAdmin):
    list_display = ("account", "txn_type", "amount", "remaining", "due_date", "status")


@admin.register(EMI)
class EMIAdmin(admin.ModelAdmin):
    list_display = ("entry", "amount", "due_date", "paid")


@admin.register(Penalty)
class PenaltyAdmin(admin.ModelAdmin):
    list_display = ("entry", "amount", "reason", "applied_at")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("lead_status", "name", "mobile", "email", "created_at", "assigned_to", "forwarded_to_admin")
    list_filter = ("forwarded_to_admin", "assigned_to", "created_at")
    search_fields = ("name", "mobile", "email", "message")
    ordering = ("forwarded_to_admin", "-created_at")
    date_hierarchy = "created_at"
    actions = ("mark_selected_reviewed", "mark_selected_new")

    def lead_status(self, obj):
        if obj.forwarded_to_admin:
            return format_html(
                '<span style="display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;background:#ecfdf5;color:#047857;font-weight:700;">'
                '<span style="font-size:14px;">✓</span> Seen</span>'
            )
        return format_html(
            '<span style="display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;background:#fff7ed;color:#c2410c;font-weight:800;border:1px solid #fed7aa;">'
            '<span style="font-size:14px;">🔔</span> New Lead</span>'
        )

    lead_status.short_description = "Lead"

    def mark_selected_reviewed(self, request, queryset):
        queryset.update(forwarded_to_admin=True)
        self.message_user(request, f"{queryset.count()} lead(s) marked as reviewed.")

    mark_selected_reviewed.short_description = "Mark selected leads as reviewed"

    def mark_selected_new(self, request, queryset):
        queryset.update(forwarded_to_admin=False)
        self.message_user(request, f"{queryset.count()} lead(s) marked as new.")

    mark_selected_new.short_description = "Mark selected leads as new"


# ====
# LOGIN LINKS & REMINDERS
# ====

@admin.register(LoginLink)
class LoginLinkAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "expires_at", "is_active", "last_used_at", "created_at")
    list_filter = ("purpose", "is_active")
    search_fields = ("user__email", "user__mobile", "token")
    readonly_fields = ("token", "created_at", "last_used_at")


@admin.register(ReminderLog)
class ReminderLogAdmin(admin.ModelAdmin):
    list_display = ("party", "reminder_type", "channel", "status", "scheduled_for", "sent_at")
    list_filter = ("reminder_type", "channel", "status")
    search_fields = ("party__name", "party__mobile")
    readonly_fields = ("created_at",)


# ====
# FIELD AGENTS & VISITS
# ====

@admin.register(FieldAgent)
class FieldAgentAdmin(admin.ModelAdmin):
    list_display = ("user", "owner", "role", "mobile", "is_active", "created_at", "agent_login_link_button")
    list_filter = ("role", "is_active")
    search_fields = ("user__email", "user__mobile", "owner__email")
    actions = ["generate_agent_login_link"]

    def agent_login_link_button(self, obj):
        return format_html(
            '<a class="button" href="{}">Login Link</a>',
            f"{obj.id}/generate-login-link/"
        )
    agent_login_link_button.short_description = "Login Link"

    def _create_agent_login_link(self, request, agent):
        mobile = agent.mobile or agent.user.mobile
        if not mobile:
            return None, "missing_mobile"

        link = LoginLink.objects.create(
            user=agent.user,
            purpose="dashboard",
            expires_at=timezone.now() + timedelta(days=7)
        )
        url = request.build_absolute_uri(
            reverse("accounts:login_link", args=[link.token])
        )
        message = f"Click here for more details 👉 {url}"

        OfflineMessage.objects.create(
            party=None,
            recipient_name=agent.user.get_full_name() or agent.user.email,
            recipient_mobile=mobile,
            message=message,
            channel="whatsapp",
            status="pending"
        )
        return link, None

    def generate_agent_login_link(self, request, queryset):
        created = 0
        skipped = 0
        for agent in queryset:
            link, error = self._create_agent_login_link(request, agent)
            if error == "missing_mobile":
                skipped += 1
                continue
            if link:
                created += 1
        if created:
            self.message_user(request, f"Generated {created} agent login link(s).")
        if skipped:
            self.message_user(request, f"Skipped {skipped} agent(s) without mobile.", level="warning")

    generate_agent_login_link.short_description = "Generate agent login link (queue)"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:agent_id>/generate-login-link/",
                self.admin_site.admin_view(self.generate_login_link_view),
                name="fieldagent_generate_login_link"
            ),
        ]
        return custom_urls + urls

    def generate_login_link_view(self, request, agent_id):
        agent = get_object_or_404(FieldAgent, id=agent_id)
        link, error = self._create_agent_login_link(request, agent)
        if error == "missing_mobile":
            self.message_user(request, "Agent has no mobile number.", level="warning")
        else:
            self.message_user(request, "Agent login link queued.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@admin.register(CollectorVisit)
class CollectorVisitAdmin(admin.ModelAdmin):
    list_display = ("party", "agent", "visit_date", "expected_amount", "collected_amount", "status")
    list_filter = ("status", "visit_date")
    search_fields = ("party__name", "agent__user__email", "agent__user__mobile")


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ("supplier", "order", "amount", "payment_mode", "payment_date", "reference")
    list_filter = ("payment_mode", "payment_date")
    search_fields = ("supplier__name", "order__invoice_number", "reference")
    readonly_fields = ("created_at",)


@admin.register(StockLedger)
class StockLedgerAdmin(admin.ModelAdmin):
    list_display = ("product", "order", "ledger_type", "quantity", "remaining_quantity", "unit_price", "created_at")
    list_filter = ("ledger_type", "created_at")
    search_fields = ("product__name", "product__sku", "order__invoice_number")
    readonly_fields = ("created_at",)


# ====
# CENTRAL BUSINESS ENGINE (BusinessGrowthEngine)
# ====


@admin.register(EngineControlPanelSettings)
class EngineControlPanelSettingsAdmin(SingletonModelAdmin):
    pass


@admin.register(BusinessGrowthEngine)
class BusinessGrowthEngineAdmin(admin.ModelAdmin):
    list_display = (
        "owner",
        "level",
        "daily_task_streak",
        "total_rewards",
        "reward_points",
        "referral_earnings",
        "payment_commission_earned",
        "whatsapp_credits",
        "loyalty_points",
        "updated_at",
    )
    search_fields = ("owner__email", "owner__username", "referral_code")
    list_filter = ("level",)
    readonly_fields = ("created_at", "updated_at", "last_reward_update")


@admin.register(RewardLedgerEntry)
class RewardLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("owner", "source", "coins_delta", "points_delta", "amount_reference", "created_at")
    list_filter = ("source",)
    search_fields = ("owner__email", "owner__username")
    readonly_fields = ("created_at",)


@admin.register(ReferralRecord)
class ReferralRecordAdmin(admin.ModelAdmin):
    list_display = ("referrer", "referred", "status", "commission_amount", "created_at", "paid_at")
    list_filter = ("status",)
    search_fields = ("referrer__email", "referred__email", "referrer__username", "referred__username")


@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ("owner", "party", "points", "cashback_total", "updated_at")
    search_fields = ("owner__email", "party__name")


@admin.register(LoyaltyLedgerEntry)
class LoyaltyLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("owner", "source", "points_delta", "cashback_delta", "created_at")
    list_filter = ("source",)
    search_fields = ("owner__email",)


@admin.register(DailyTaskDefinition)
class DailyTaskDefinitionAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "is_active", "coins_reward", "points_reward", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("key", "title")


@admin.register(DailyTaskCompletion)
class DailyTaskCompletionAdmin(admin.ModelAdmin):
    list_display = ("owner", "task", "day", "completed_at")
    list_filter = ("day",)
    search_fields = ("owner__email", "owner__username", "task__key")


@admin.register(EngineEventLog)
class EngineEventLogAdmin(admin.ModelAdmin):
    list_display = ("owner", "category", "level", "event_key", "created_at")
    list_filter = ("category", "level")
    search_fields = ("owner__email", "event_key", "message")
    readonly_fields = ("created_at",)
