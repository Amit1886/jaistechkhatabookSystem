# khataapp/utils/whatsapp_utils.py

# Backward-compatible defaults (used only if core settings are not configured).
INSTANCE_ID = "instance136750"
TOKEN = "opqr2t6es4k43x9o"

def send_whatsapp_message(to, message):
    """
    UltraMsg docs: https://docs.ultramsg.com/
    to: string without '+'; e.g. 9199xxxxxxx
    """
    import requests

    try:
        from core_settings.customer_login_link import maybe_append_customer_login_link

        message = maybe_append_customer_login_link(
            channel="whatsapp", recipient=str(to or ""), message=str(message or ""), purpose="generic"
        )
    except Exception:
        pass

    # Prefer centralized, configurable connector if available.
    try:
        from whatsapp.api_connector import send_whatsapp_message as _send  # type: ignore

        res = _send(to=str(to or ""), message=str(message or ""))
        # If configured + attempted, return its result.
        if res.status_code not in {400} or "not configured" not in (res.response_text or "").lower():
            return int(res.status_code or 0), str(res.response_text or "")
    except Exception:
        # Fall back to legacy constants below.
        pass

    url = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"
    payload = {"to": str(to or "").lstrip("+"), "body": str(message or "")}
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Authorization": f"Bearer {TOKEN}"}
    resp = requests.post(url, data=payload, headers=headers, timeout=20)
    return resp.status_code, resp.text

