import logging
from django.conf import settings
from .models import OfflineMessage  # âœ… make sure you created OfflineMessage in models.py

logger = logging.getLogger(__name__)


def send_whatsapp_message(number, message):
    """
    Try to send WhatsApp message via API.
    If network/API fails, save to OfflineMessage.
    """
    import requests

    if not getattr(settings, "WHATSAPP_API_KEY", None):
        logger.warning("WhatsApp API key not found in settings.")
        return False

    url = f"https://api.ultramsg.com/{settings.WHATSAPP_INSTANCE_ID}/messages/chat"
    payload = {
        "token": settings.WHATSAPP_API_KEY,   # âœ… dynamic from settings
        "to": f"+91{number}",
        "body": message
    }

    try:
        r = requests.post(url, data=payload, timeout=5)
        r.raise_for_status()
        return r.status_code == 200
    except Exception as e:
        logger.error(f"WhatsApp send failed: {e}")
        # fallback â†’ save in DB
        OfflineMessage.objects.create(
            party=None,  # à¤…à¤—à¤° à¤†à¤ªà¤•à¥‡ à¤ªà¤¾à¤¸ Party object à¤¹à¥ˆ à¤¤à¥‹ pass à¤•à¤°à¥‡à¤‚
            message=message,
            channel="whatsapp",
            status="pending"
        )
        return False


def send_sms(number, message):
    """
    Try to send SMS via API.
    If network/API fails, save to OfflineMessage.
    """
    import requests

    if not getattr(settings, "SMS_API_KEY", None):
        logger.warning("SMS API key not found in settings.")
        return False

    url = "https://www.fast2sms.com/dev/bulkV2"
    payload = {
        "authorization": settings.SMS_API_KEY,  # âœ… dynamic from settings
        "route": "q",
        "message": message,
        "language": "english",
        "flash": 0,
        "numbers": number
    }
    headers = {'cache-control': "no-cache"}

    try:
        r = requests.post(url, data=payload, headers=headers, timeout=5)
        r.raise_for_status()
        return r.status_code == 200
    except Exception as e:
        logger.error(f"SMS send failed: {e}")
        # fallback â†’ save in DB
        OfflineMessage.objects.create(
            party=None,  # à¤…à¤—à¤° à¤†à¤ªà¤•à¥‡ à¤ªà¤¾à¤¸ Party object à¤¹à¥ˆ à¤¤à¥‹ pass à¤•à¤°à¥‡à¤‚
            message=message,
            channel="sms",
            status="pending"
        )
        return False

