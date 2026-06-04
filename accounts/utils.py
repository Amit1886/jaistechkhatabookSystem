# accounts/utils.py
from django.core.mail import send_mail
import requests
from django.conf import settings
from io import BytesIO
import urllib.parse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from django.template.loader import get_template
from django.contrib.staticfiles import finders
import os
try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None
from khataapp.models import Transaction
from django.utils import timezone
from django.db.models import Sum
from accounts.models import DailySummary



def send_email_otp(to_email, code):
    subject = "Your OTP Code"
    body = f"Your verification code is: {code}"
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=True)

def send_sms_otp(mobile, code, api_key=None):
    if not mobile:
        return
    api_key = api_key or getattr(settings, "FAST2SMS_API_KEY", None)
    if not api_key:
        return
    url = (
        "https://www.fast2sms.com/dev/bulkV2?"
        f"authorization={api_key}&route=q&message=Your%20OTP%20is%20{code}"
        f"&language=english&flash=0&numbers={mobile}"
    )
    try:
        requests.get(url, headers={"cache-control": "no-cache"}, timeout=20)
    except Exception:
        pass

def render_to_pdf_bytes(template_src, context_dict=None, *, request=None):
    """Render HTML template into PDF bytes (xhtml2pdf)."""
    if pisa is None:
        return None

    def _link_callback(uri, rel):
        """
        Resolve /static/ and /media/ URIs into absolute file system paths for xhtml2pdf.
        """
        try:
            if uri.startswith(getattr(settings, "MEDIA_URL", "/media/")):
                path = os.path.join(getattr(settings, "MEDIA_ROOT", ""), uri.replace(getattr(settings, "MEDIA_URL", "/media/"), ""))
                if os.path.isfile(path):
                    return path

            if uri.startswith(getattr(settings, "STATIC_URL", "/static/")):
                static_path = finders.find(uri.replace(getattr(settings, "STATIC_URL", "/static/"), ""))
                if isinstance(static_path, (list, tuple)):
                    static_path = static_path[0] if static_path else None
                if static_path and os.path.isfile(static_path):
                    return static_path

            if uri.startswith("http://") or uri.startswith("https://"):
                return uri

            # Already a local path?
            if os.path.isfile(uri):
                return uri
        except Exception:
            pass
        return uri

    context_dict = context_dict or {}
    template = get_template(template_src)
    html = template.render(context_dict, request=request) if request is not None else template.render(context_dict)

    result = BytesIO()
    pdf = pisa.CreatePDF(html, dest=result, link_callback=_link_callback)

    if not pdf.err:
        return result.getvalue()

    return None

def whatsapp_message_url(mobile_number, message_text):
    """
    Returns a whatsapp wa.me link which opens chat with prefilled text.
    mobile_number: string with country code, e.g. 91XXXXXXXXXX
    message_text: plain text
    """
    text = urllib.parse.quote(message_text)
    # Ensure mobile_number has only digits, include country code (e.g. 91)
    number = ''.join(ch for ch in (mobile_number or '') if ch.isdigit())
    return f"https://wa.me/{number}?text={text}"


def update_daily_summary(user):

    if user is None or not hasattr(user, "id"):
        return None

    today = timezone.now().date()

    transactions = Transaction.objects.filter(
        party__owner=user,
        date=today
    )

    total_credit = transactions.filter(txn_type="credit").aggregate(total=Sum("amount"))["total"] or 0
    total_debit = transactions.filter(txn_type="debit").aggregate(total=Sum("amount"))["total"] or 0
    balance = total_debit - total_credit
    total_transactions = transactions.count()

    summary, created = DailySummary.objects.get_or_create(
        user=user,
        date=today,
        defaults={
            "total_credit": total_credit,
            "total_debit": total_debit,
            "balance": balance,
            "total_transactions": total_transactions
        }
    )

    # Update old summary
    summary.total_credit = total_credit
    summary.total_debit = total_debit
    summary.balance = balance
    summary.total_transactions = total_transactions
    summary.save()

    return summary
