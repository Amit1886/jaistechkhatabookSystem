from django.contrib.auth.models import Group
from django.db import transaction, OperationalError
from django.core.cache import cache

from core_settings.models import (
    SettingCategory,
    SettingDefinition,
    SettingPermission,
    SettingValue,
    SettingHistory,
)


SETTINGS_REGISTRY = [
    {
        "slug": "user_account",
        "label": "User & Account",
        "icon": "user",
        "description": "Profile, login security, and personalization.",
        "settings": [
            {"key": "user_profile_edit", "label": "Profile editable", "data_type": "boolean", "default": True, "scope": "user"},
            {"key": "user_change_password", "label": "Password change", "data_type": "boolean", "default": True, "scope": "user"},
            {"key": "user_2fa_enabled", "label": "2FA / OTP", "data_type": "boolean", "default": False, "scope": "user"},
            {"key": "user_role_visibility", "label": "Role visibility", "data_type": "boolean", "default": True, "scope": "user"},
            {"key": "user_login_logs", "label": "Login security logs", "data_type": "boolean", "default": True, "scope": "user"},
            {"key": "user_session_control", "label": "Session control", "data_type": "boolean", "default": True, "scope": "user"},
            {"key": "user_theme", "label": "Theme", "data_type": "select", "default": "light", "options": ["light", "dark"], "scope": "user"},
            {"key": "user_language", "label": "Language", "data_type": "select", "default": "en", "options": ["en", "hi", "gu", "mr"], "scope": "user"},
        ],
    },
    {
        "slug": "company",
        "label": "Company",
        "icon": "building",
        "description": "Business identity, legal, and banking.",
        "settings": [
            {"key": "company_name", "label": "Company name", "data_type": "string", "default": "My Business"},
            {"key": "company_logo", "label": "Company logo URL", "data_type": "string", "default": ""},
            {"key": "company_gst", "label": "GST number", "data_type": "string", "default": ""},
            {"key": "company_cin", "label": "CIN", "data_type": "string", "default": ""},
            {"key": "company_address", "label": "Address", "data_type": "text", "default": ""},
            {"key": "company_contact", "label": "Contact info", "data_type": "text", "default": ""},
            {"key": "company_bank_details", "label": "Bank details", "data_type": "text", "default": ""},
            {"key": "company_digital_signature", "label": "Digital signature URL", "data_type": "string", "default": ""},
            {"key": "company_invoice_footer", "label": "Invoice footer notes", "data_type": "text", "default": ""},
            {"key": "company_terms", "label": "Terms & conditions", "data_type": "text", "default": ""},
            {"key": "company_currency", "label": "Default currency", "data_type": "select", "default": "INR", "options": ["INR", "USD", "EUR", "GBP"]},
            {"key": "company_timezone", "label": "Timezone", "data_type": "select", "default": "Asia/Kolkata", "options": ["Asia/Kolkata", "UTC", "America/New_York"]},
        ],
    },
    {
        "slug": "financial",
        "label": "Financial",
        "icon": "calculator",
        "description": "Fiscal year, ledgers, and currency rules.",
        "settings": [
            {"key": "financial_year", "label": "Financial year start", "data_type": "date", "default": ""},
            {"key": "opening_balances", "label": "Opening balances", "data_type": "json", "default": {}},
            {"key": "ledger_defaults", "label": "Ledger defaults", "data_type": "json", "default": {}},
            {"key": "account_groups", "label": "Account groups", "data_type": "json", "default": []},
            {"key": "chart_of_accounts", "label": "Chart of accounts", "data_type": "json", "default": []},
            {"key": "default_tax_mode", "label": "Default tax mode", "data_type": "select", "default": "exclusive", "options": ["inclusive", "exclusive"]},
            {"key": "rounding_rules", "label": "Rounding rules", "data_type": "select", "default": "nearest", "options": ["nearest", "up", "down"]},
            {"key": "multi_currency", "label": "Multi-currency enable", "data_type": "boolean", "default": False},
        ],
    },
    {
        "slug": "khata_control",
        "label": "Khata Control",
        "icon": "bell",
        "description": "Smart khata credit score + auto payment reminders.",
        "settings": [
            {
                "key": "khata_auto_reminders_enabled",
                "label": "Enable auto khata reminders",
                "data_type": "boolean",
                "default": True,
                "scope": "user",
                "help_text": "Master switch for due/payment reminder automation.",
            },
            {
                "key": "khata_reminder_offsets",
                "label": "Reminder schedule offsets (days)",
                "data_type": "json",
                "default": [-3, 0, 3, 7],
                "scope": "user",
                "help_text": "Offsets relative to due date. Example: [-3,0,3,7].",
            },
            {
                "key": "khata_smart_timing_enabled",
                "label": "Enable smart reminder timing",
                "data_type": "boolean",
                "default": True,
                "scope": "user",
                "help_text": "Learns typical delay and sends a reminder 1 day before the usual payment day.",
            },
            {
                "key": "khata_default_tone",
                "label": "Default reminder tone",
                "data_type": "select",
                "default": "professional",
                "options": ["friendly", "professional", "strict"],
                "scope": "user",
            },
            {
                "key": "khata_reminder_channels",
                "label": "Reminder channels",
                "data_type": "json",
                "default": ["whatsapp"],
                "scope": "user",
                "help_text": "Example: [\"whatsapp\",\"sms\",\"email\"].",
            },
            {
                "key": "khata_template_friendly",
                "label": "Reminder template (Friendly)",
                "data_type": "text",
                "default": "Hello {{customer_name}}, your outstanding balance of ₹{{amount}} is pending since {{days}} days. Please clear your payment. Thank you.",
                "scope": "user",
            },
            {
                "key": "khata_template_professional",
                "label": "Reminder template (Professional)",
                "data_type": "text",
                "default": "Hello {{customer_name}}, your outstanding balance of ₹{{amount}} is pending for {{days}} days. Kindly make the payment at the earliest. Invoice: {{invoice_number}}.",
                "scope": "user",
            },
            {
                "key": "khata_template_strict",
                "label": "Reminder template (Strict)",
                "data_type": "text",
                "default": "Dear {{customer_name}}, payment of ₹{{amount}} is overdue by {{days}} days. Please pay immediately to avoid further action. Invoice: {{invoice_number}}.",
                "scope": "user",
            },
            {
                "key": "khata_risk_threshold",
                "label": "High-risk score threshold",
                "data_type": "number",
                "default": 40,
                "scope": "user",
                "help_text": "Score below this value triggers warnings (default 40).",
            },
        ],
    },
    {
        "slug": "invoice_voucher",
        "label": "Invoice & Voucher",
        "icon": "file-text",
        "description": "Numbering, formats, and auto rules.",
        "settings": [
            {"key": "invoice_series", "label": "Invoice series generator", "data_type": "string", "default": "INV-2026-0001"},
            {"key": "voucher_numbering", "label": "Voucher numbering rules", "data_type": "string", "default": "VCH-YYYY-####"},
            {"key": "prefix_suffix", "label": "Prefix / suffix pattern", "data_type": "string", "default": ""},
            {"key": "auto_numbering", "label": "Auto numbering", "data_type": "boolean", "default": True},
            {"key": "credit_note_format", "label": "Credit/Debit note format", "data_type": "string", "default": "CN-YYYY-####"},
            {"key": "estimate_format", "label": "Estimate / Proforma format", "data_type": "string", "default": "EST-YYYY-####"},
            {"key": "auto_due_date_rule", "label": "Auto due date rules (days)", "data_type": "number", "default": 15},
        ],
    },
    {
        "slug": "item_inventory",
        "label": "Item & Inventory",
        "icon": "package",
        "description": "Products, categories, and stock rules.",
        "settings": [
            {"key": "item_code_format", "label": "Item code format", "data_type": "string", "default": "ITEM-####"},
            {"key": "barcode_rules", "label": "Barcode rules", "data_type": "string", "default": ""},
            {"key": "sku_generator", "label": "SKU generator", "data_type": "string", "default": "SKU-####"},
            {"key": "item_categories", "label": "Item categories", "data_type": "json", "default": []},
            {"key": "units_conversions", "label": "Units & conversions", "data_type": "json", "default": []},
            {"key": "low_stock_alert", "label": "Low stock alert (qty)", "data_type": "number", "default": 5},
            {"key": "batch_expiry", "label": "Batch & expiry", "data_type": "boolean", "default": False},
            {"key": "serial_tracking", "label": "Serial number tracking", "data_type": "boolean", "default": False},
        ],
    },
    {
        "slug": "printer_label",
        "label": "Printer & Label",
        "icon": "printer",
        "description": "Printer setup and label layouts.",
        "settings": [
            {"key": "invoice_printer", "label": "Invoice printer setup", "data_type": "string", "default": ""},
            {"key": "thermal_mode", "label": "Thermal printer mode", "data_type": "boolean", "default": False},
            {"key": "page_size", "label": "Page size", "data_type": "select", "default": "A4", "options": ["A4", "A5", "Letter", "Thermal-80mm"]},
            {"key": "print_templates", "label": "Print templates", "data_type": "json", "default": []},
            {"key": "label_printing", "label": "Label printing", "data_type": "boolean", "default": False},
            {"key": "barcode_label_layout", "label": "Barcode label layout", "data_type": "string", "default": ""},
            {"key": "qr_code_printing", "label": "QR code printing", "data_type": "boolean", "default": True},
            {"key": "bulk_label_print", "label": "Bulk label print", "data_type": "boolean", "default": False},
        ],
    },
    {
        "slug": "scanner_barcode",
        "label": "Scanner & Barcode",
        "icon": "scan",
        "description": "Scan mapping and fast scan behavior.",
        "settings": [
            {"key": "scanner_mapping", "label": "Barcode scanner mapping", "data_type": "json", "default": {}},
            {"key": "camera_scan", "label": "Camera scan mode", "data_type": "boolean", "default": False},
            {"key": "fast_scan", "label": "Fast scan toggle", "data_type": "boolean", "default": True},
            {"key": "auto_add_on_scan", "label": "Auto add on scan", "data_type": "boolean", "default": True},
            {"key": "scan_to_cart", "label": "Scan-to-cart behavior", "data_type": "select", "default": "add", "options": ["add", "replace", "confirm"]},
        ],
    },
    {
        "slug": "whatsapp_comm",
        "label": "WhatsApp & Communication",
        "icon": "message-circle",
        "description": "Messaging, reminders, and email/SMS.",
        "settings": [
            {"key": "whatsapp_api_config", "label": "WhatsApp API config", "data_type": "text", "default": ""},
            {"key": "wa_enabled", "label": "Enable WhatsApp automation", "data_type": "boolean", "default": True, "help_text": "Master switch for WhatsApp automation features."},
            {
                "key": "wa_provider",
                "label": "WhatsApp provider",
                "data_type": "select",
                "default": "ultramsg",
                "options": [
                    {"value": "ultramsg", "label": "UltraMsg (easy demo)"},
                    {"value": "meta_cloud_api", "label": "Meta WhatsApp Cloud API (official)"},
                    {"value": "twilio", "label": "Twilio WhatsApp"},
                    {"value": "gupshup", "label": "Gupshup (BSP)"},
                    {"value": "360dialog", "label": "360dialog (BSP)"},
                    {"value": "wati", "label": "WATI (BSP/platform)"},
                    {"value": "interakt", "label": "Interakt (BSP/platform)"},
                    {"value": "aisensy", "label": "AiSensy (BSP/platform)"},
                    {"value": "infobip", "label": "Infobip (BSP)"},
                    {"value": "vonage", "label": "Vonage (BSP)"},
                    {"value": "messagebird", "label": "MessageBird/Bird (BSP)"},
                    {"value": "kaleyra", "label": "Kaleyra (BSP)"},
                    {"value": "custom_http", "label": "Custom HTTP (any provider)"},
                ],
                "help_text": "Select your WhatsApp provider. For most market vendors you can use Custom HTTP, or use Meta/Twilio if you have official credentials.",
            },
            {"key": "wa_ultramsg_instance_id", "label": "UltraMsg Instance ID", "data_type": "string", "default": "", "help_text": "Example: instance123456"},
            {"key": "wa_ultramsg_token", "label": "UltraMsg Token", "data_type": "string", "default": "", "help_text": "Bearer token / API token from UltraMsg."},
            {"key": "wa_meta_phone_number_id", "label": "Meta Phone Number ID", "data_type": "string", "default": "", "help_text": "WhatsApp Cloud API phone_number_id."},
            {"key": "wa_meta_access_token", "label": "Meta Access Token", "data_type": "string", "default": "", "help_text": "Permanent/long-lived access token for WhatsApp Cloud API."},
            {"key": "wa_meta_graph_version", "label": "Meta Graph API version", "data_type": "string", "default": "v20.0", "help_text": "Example: v20.0 (change if your app uses a different version)."},
            {"key": "wa_twilio_account_sid", "label": "Twilio Account SID", "data_type": "string", "default": "", "help_text": "Example: ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"},
            {"key": "wa_twilio_auth_token", "label": "Twilio Auth Token", "data_type": "string", "default": "", "help_text": "Twilio auth token."},
            {"key": "wa_twilio_from_number", "label": "Twilio From (WhatsApp)", "data_type": "string", "default": "", "help_text": "Example: whatsapp:+14155238886"},
            {"key": "wa_custom_send_url", "label": "Custom provider send URL", "data_type": "string", "default": "", "help_text": "For Custom HTTP: the message send endpoint URL."},
            {"key": "wa_custom_content_type", "label": "Custom provider content type", "data_type": "select", "default": "form", "options": ["form", "json"], "help_text": "For Custom HTTP: how to send the payload."},
            {"key": "wa_custom_to_field", "label": "Custom provider 'to' field", "data_type": "string", "default": "to", "help_text": "For Custom HTTP: field name for destination number."},
            {"key": "wa_custom_body_field", "label": "Custom provider 'body' field", "data_type": "string", "default": "body", "help_text": "For Custom HTTP: field name for message text."},
            {"key": "wa_custom_extra_payload", "label": "Custom provider extra payload", "data_type": "json", "default": {}, "help_text": "For Custom HTTP: extra JSON fields to include in the request body."},
            {"key": "wa_custom_headers", "label": "Custom provider headers", "data_type": "json", "default": {}, "help_text": "For Custom HTTP: extra request headers (JSON object)."},
            {"key": "wa_custom_auth_header", "label": "Custom provider auth header", "data_type": "string", "default": "Authorization", "help_text": "For Custom HTTP: header name for auth."},
            {"key": "wa_custom_auth_value", "label": "Custom provider auth value", "data_type": "string", "default": "", "help_text": "For Custom HTTP: header value, e.g. 'Bearer <token>'."},
            {"key": "wa_webhook_secret", "label": "WhatsApp webhook secret", "data_type": "string", "default": "", "help_text": "Shared secret to protect the webhook endpoint."},
            {"key": "order_via_whatsapp", "label": "Order via WhatsApp", "data_type": "boolean", "default": False},
            {"key": "invoice_share_auto", "label": "Invoice share automation", "data_type": "boolean", "default": False},
            {"key": "payment_link_auto", "label": "Payment link auto-send", "data_type": "boolean", "default": False},
            {"key": "reminder_templates", "label": "Reminder templates", "data_type": "json", "default": []},
            {"key": "chatbot_order_mode", "label": "Chatbot order mode", "data_type": "boolean", "default": False},

            # ---------------- OTP (SMS/Email/WhatsApp) ----------------
            {
                "key": "otp_delivery_strategy",
                "label": "OTP delivery strategy",
                "data_type": "select",
                "default": "all",
                "options": [
                    {"value": "all", "label": "Send via all enabled channels"},
                    {"value": "fallback", "label": "Fallback (try SMS, then Email, then WhatsApp)"},
                ],
                "help_text": "Controls how OTP is delivered. 'All' is best for reliability; 'Fallback' reduces message volume.",
            },
            {"key": "otp_send_via_sms", "label": "Send OTP via SMS", "data_type": "boolean", "default": True},
            {"key": "otp_send_via_email", "label": "Send OTP via Email", "data_type": "boolean", "default": True},
            {"key": "otp_send_via_whatsapp", "label": "Send OTP via WhatsApp", "data_type": "boolean", "default": True},

            # ---------------- SMS Provider ----------------
            {
                "key": "sms_provider",
                "label": "SMS provider",
                "data_type": "select",
                "default": "fast2sms",
                "options": [
                    {"value": "demo", "label": "Demo (no real SMS, just logs)"},
                    {"value": "fast2sms", "label": "Fast2SMS (quick demo)"},
                    {"value": "google", "label": "Google Verified SMS / RCS (via gateway)"},
                    {"value": "custom_http", "label": "Custom HTTP (any SMS gateway)"},
                ],
                "help_text": "Choose how the platform sends SMS (OTP + public download links).",
            },
            {"key": "sms_api_key", "label": "SMS API key", "data_type": "string", "default": "", "help_text": "API key/token for your SMS provider (used by Fast2SMS/Google/custom providers)."},
            {"key": "sms_sender_id", "label": "SMS Sender ID", "data_type": "string", "default": "", "help_text": "DLT sender ID (if your provider requires it). Example: BILLEN"},
            {"key": "sms_api_url", "label": "SMS API URL", "data_type": "string", "default": "", "help_text": "Optional override URL for SMS provider (used by Google/custom providers)."},
            {"key": "sms_dlt_enabled", "label": "Enable DLT mode", "data_type": "boolean", "default": False, "help_text": "Enable if your SMS provider requires DLT entity/template IDs (India)."},
            {"key": "sms_dlt_entity_id", "label": "DLT Entity ID", "data_type": "string", "default": "", "help_text": "Your DLT entity ID (if applicable)."},
            {"key": "sms_dlt_template_id_otp", "label": "DLT Template ID (OTP)", "data_type": "string", "default": "", "help_text": "Your approved DLT template ID for OTP messages (if applicable)."},

            # Custom HTTP SMS adapter (works for most providers)
            {"key": "sms_custom_send_url", "label": "Custom SMS send URL", "data_type": "string", "default": "", "help_text": "For Custom HTTP: the SMS send endpoint URL."},
            {"key": "sms_custom_method", "label": "Custom SMS method", "data_type": "select", "default": "POST", "options": ["POST", "GET"], "help_text": "For Custom HTTP: HTTP method."},
            {"key": "sms_custom_content_type", "label": "Custom SMS content type", "data_type": "select", "default": "form", "options": ["form", "json"], "help_text": "For Custom HTTP: send payload as form or JSON."},
            {"key": "sms_custom_to_field", "label": "Custom SMS 'to' field", "data_type": "string", "default": "to", "help_text": "For Custom HTTP: payload field name for destination number."},
            {"key": "sms_custom_message_field", "label": "Custom SMS 'message' field", "data_type": "string", "default": "message", "help_text": "For Custom HTTP: payload field name for message text."},
            {"key": "sms_custom_headers", "label": "Custom SMS headers", "data_type": "json", "default": {}, "help_text": "For Custom HTTP: request headers (JSON object)."},
            {"key": "sms_custom_auth_header", "label": "Custom SMS auth header", "data_type": "string", "default": "Authorization", "help_text": "For Custom HTTP: header name for auth."},
            {"key": "sms_custom_auth_value", "label": "Custom SMS auth value", "data_type": "string", "default": "", "help_text": "For Custom HTTP: header value, e.g. 'Bearer <token>'."},
            {"key": "sms_custom_extra_payload", "label": "Custom SMS extra payload", "data_type": "json", "default": {}, "help_text": "For Custom HTTP: extra fields to include in the request body."},

            # ---------------- Email SMTP (Optional) ----------------
            {"key": "smtp_host", "label": "SMTP Host", "data_type": "string", "default": "", "help_text": "If set, OTP emails use this SMTP config instead of default Django email settings."},
            {"key": "smtp_port", "label": "SMTP Port", "data_type": "number", "default": 587},
            {"key": "smtp_username", "label": "SMTP Username", "data_type": "string", "default": ""},
            {"key": "smtp_password", "label": "SMTP Password", "data_type": "string", "default": ""},
            {"key": "smtp_use_tls", "label": "SMTP Use TLS", "data_type": "boolean", "default": True},
            {"key": "smtp_use_ssl", "label": "SMTP Use SSL", "data_type": "boolean", "default": False},
            {"key": "smtp_from_email", "label": "From Email", "data_type": "string", "default": "", "help_text": "From address for OTP emails. Falls back to DEFAULT_FROM_EMAIL."},
            {"key": "sms_gateway_config", "label": "SMS gateway config", "data_type": "text", "default": ""},
            {"key": "email_smtp_config", "label": "Email SMTP config", "data_type": "text", "default": ""},

            # ---------------- Customer Login Link Footer ----------------
            {
                "key": "public_base_url",
                "label": "Public Base URL",
                "data_type": "string",
                "default": "",
                "help_text": "Optional. Example: https://app.yourdomain.com (used in WhatsApp/SMS login links).",
            },
            {"key": "customer_login_link_enabled", "label": "Append customer login link", "data_type": "boolean", "default": True},
            {"key": "customer_login_link_append_to_sms", "label": "Append to SMS", "data_type": "boolean", "default": True},
            {"key": "customer_login_link_append_to_whatsapp", "label": "Append to WhatsApp", "data_type": "boolean", "default": True},
            {"key": "customer_login_link_append_to_email", "label": "Append to Email", "data_type": "boolean", "default": True},
            {"key": "customer_login_link_append_to_notifications", "label": "Append to Notifications", "data_type": "boolean", "default": True},
            {"key": "customer_login_link_append_to_otp", "label": "Append to OTP messages", "data_type": "boolean", "default": False},
            {"key": "customer_login_link_expires_hours", "label": "Login link expiry (hours)", "data_type": "number", "default": 168},
            {
                "key": "customer_login_link_footer_template",
                "label": "Login link footer template",
                "data_type": "text",
                "default": "\n\nLogin: {url}",
                "help_text": "Use {url}. Example: \\n\\nOpen your dashboard: {url}",
            },
        ],
    },
    {
        "slug": "social_integration",
        "label": "Social & Integration",
        "icon": "share-2",
        "description": "Links, API keys, and webhooks.",
        "settings": [
            {"key": "social_links", "label": "Social media links", "data_type": "json", "default": {}},
            {"key": "website_link", "label": "Website link", "data_type": "string", "default": ""},
            {"key": "google_login", "label": "Google login", "data_type": "boolean", "default": False},
            {"key": "api_keys_manager", "label": "API keys manager", "data_type": "json", "default": {}},
            # ---------------- Shopify (Partner App) ----------------
            {"key": "shopify_client_id", "label": "Shopify Client ID", "data_type": "string", "default": "", "help_text": "From Shopify Dev Dashboard app settings."},
            {"key": "shopify_client_secret", "label": "Shopify Client Secret", "data_type": "string", "default": "", "help_text": "Store securely. Used to verify OAuth and exchange token."},
            {"key": "shopify_scopes", "label": "Shopify Scopes", "data_type": "string", "default": "read_orders,read_products,read_customers", "help_text": "Comma-separated scopes for OAuth authorize URL."},
            {"key": "shopify_webhook_secret", "label": "Shopify Webhook Secret", "data_type": "string", "default": "", "help_text": "Optional: shared secret for verifying webhook requests."},
            {"key": "webhook_settings", "label": "Webhook settings", "data_type": "json", "default": {}},
            {"key": "third_party_integrations", "label": "Third-party integrations", "data_type": "json", "default": []},
        ],
    },
    {
        "slug": "tax_compliance",
        "label": "Tax & Compliance",
        "icon": "shield",
        "description": "GST, HSN/SAC, and filing reminders.",
        "settings": [
            {"key": "tax_categories", "label": "Tax categories", "data_type": "json", "default": []},
            {"key": "gst_slabs", "label": "GST slabs", "data_type": "json", "default": []},
            {"key": "hsn_sac_mapping", "label": "HSN/SAC mapping", "data_type": "json", "default": {}},
            {"key": "tax_inclusive_mode", "label": "Tax inclusive/exclusive", "data_type": "select", "default": "exclusive", "options": ["inclusive", "exclusive"]},
            {"key": "region_tax_rules", "label": "Region tax rules", "data_type": "json", "default": {}},
            {"key": "filing_reminders", "label": "Filing reminder alerts", "data_type": "boolean", "default": True},
        ],
    },
    {
        "slug": "ai_tools",
        "label": "AI Tools",
        "icon": "cpu",
        "description": "AI-powered accounting, OCR and insights.",
        "settings": [
            {"key": "ai_tools_enabled", "label": "Enable AI Tools", "data_type": "boolean", "default": True},
            {"key": "ocr_enabled", "label": "Enable OCR Invoice Entry", "data_type": "boolean", "default": True},
            {"key": "ocr_model", "label": "OCR Model (OpenAI)", "data_type": "string", "default": "gpt-4o-mini"},
            {"key": "voice_enabled", "label": "Enable Voice Accounting", "data_type": "boolean", "default": True},
            {"key": "ai_insights_enabled", "label": "Enable AI Insights", "data_type": "boolean", "default": True},
            {"key": "smart_alerts_enabled", "label": "Enable Smart Alerts", "data_type": "boolean", "default": True},
        ],
    },
    {
        "slug": "automation",
        "label": "Automation",
        "icon": "zap",
        "description": "Automation rules and imports.",
        "settings": [
            {"key": "bank_import_enabled", "label": "Enable Bank Statement Import", "data_type": "boolean", "default": True},
            {
                "key": "bank_import_mapping",
                "label": "Bank Import Mapping Rules",
                "data_type": "json",
                "default": {"expenses": [{"pattern": "diesel", "category": "Fuel"}]},
                "help_text": "Regex-based mapping. Example: {'expenses':[{'pattern':'diesel','category':'Fuel'}]}",
            },
        ],
    },
    {
        "slug": "portal",
        "label": "Customer & Supplier Portal",
        "icon": "globe",
        "description": "Self-service portal access, welcome kit automation and payment links.",
        "settings": [
            {"key": "portal_enabled", "label": "Enable Portal", "data_type": "boolean", "default": True},
            {"key": "portal_customer_enabled", "label": "Enable Customer Portal", "data_type": "boolean", "default": True},
            {"key": "portal_supplier_enabled", "label": "Enable Supplier Portal", "data_type": "boolean", "default": True},
            {"key": "portal_customer_split_dashboards", "label": "Split customer dashboards (E-commerce/Billing)", "data_type": "boolean", "default": True},
            {"key": "portal_supplier_split_dashboards", "label": "Split supplier dashboards (Purchases/Billing)", "data_type": "boolean", "default": True},
            {
                "key": "portal_base_url",
                "label": "Portal Base URL",
                "data_type": "string",
                "default": "",
                "help_text": "Public URL used in welcome messages. Leave blank to use BASE_URL.",
            },
            {"key": "portal_welcome_whatsapp", "label": "Welcome kit via WhatsApp", "data_type": "boolean", "default": True},
            {"key": "portal_welcome_sms", "label": "Welcome kit via SMS", "data_type": "boolean", "default": True},
            {"key": "portal_welcome_email", "label": "Welcome kit via Email", "data_type": "boolean", "default": True},
        ],
    },
]


def get_user_role(user):
    if user.is_superuser:
        return "super_admin"

    saas_role = (getattr(user, "role", "") or "").strip().lower()
    if saas_role == "super_admin":
        return "super_admin"
    if saas_role in {"state_admin", "district_admin", "area_admin"}:
        return "admin"
    if saas_role == "super_agent":
        return "manager"
    if saas_role in {"agent", "customer"}:
        return "user"

    if user.is_staff:
        return "admin"
    manager_group = Group.objects.filter(name__iexact="manager").first()
    if manager_group and manager_group in user.groups.all():
        return "manager"
    return "user"


def sync_settings_registry():
    registry_key = "core_settings_registry_v1"
    if cache.get(registry_key):
        return

    try:
        with transaction.atomic():
            for index, category_data in enumerate(SETTINGS_REGISTRY):
                category, _ = SettingCategory.objects.update_or_create(
                    slug=category_data["slug"],
                    defaults={
                        "label": category_data["label"],
                        "description": category_data.get("description", ""),
                        "icon": category_data.get("icon", ""),
                        "sort_order": index,
                    },
                )
                for setting_index, setting in enumerate(category_data.get("settings", [])):
                    SettingDefinition.objects.update_or_create(
                        key=setting["key"],
                        defaults={
                            "category": category,
                            "label": setting["label"],
                            "help_text": setting.get("help_text", ""),
                            "data_type": setting.get("data_type", "string"),
                            "default_value": setting.get("default", ""),
                            "options": setting.get("options", []),
                            "scope": setting.get("scope", "global"),
                            "sort_order": setting_index,
                        },
                    )
                for role in ["super_admin", "admin", "manager", "user"]:
                    SettingPermission.objects.get_or_create(
                        role=role,
                        category=category,
                        defaults={"can_view": True, "can_edit": True, "hidden": False},
                    )
        cache.set(registry_key, True, 3600)
    except OperationalError:
        # Avoid crashing the request if sqlite is locked; retry later.
        cache.set(registry_key, True, 30)
        return


def _get_value_for_definition(definition, owner):
    value_obj = SettingValue.objects.filter(definition=definition, owner=owner).first()
    if value_obj:
        return value_obj.value
    return definition.default_value


def get_settings_payload(user):
    sync_settings_registry()
    role = get_user_role(user)
    categories = []
    permissions = {p.category_id: p for p in SettingPermission.objects.filter(role=role)}

    for category in SettingCategory.objects.all():
        permission = permissions.get(category.id)
        if permission and permission.hidden:
            continue
        if permission and not permission.can_view:
            continue
        settings_payload = []
        for definition in category.definitions.all():
            owner = user if definition.scope == "user" else None
            settings_payload.append(
                {
                    "key": definition.key,
                    "label": definition.label,
                    "help_text": definition.help_text,
                    "data_type": definition.data_type,
                    "value": _get_value_for_definition(definition, owner),
                    "options": definition.options or [],
                    "scope": definition.scope,
                    "editable": bool(permission.can_edit) if permission else True,
                }
            )
        categories.append(
            {
                "slug": category.slug,
                "label": category.label,
                "description": category.description,
                "icon": category.icon,
                "settings": settings_payload,
                "editable": bool(permission.can_edit) if permission else True,
            }
        )

    return {"role": role, "categories": categories}


@transaction.atomic
def apply_updates(user, updates):
    sync_settings_registry()
    role = get_user_role(user)
    permissions = {p.category_id: p for p in SettingPermission.objects.filter(role=role)}
    results = []

    for update in updates:
        key = update.get("key")
        value = update.get("value")
        if not key:
            continue
        definition = SettingDefinition.objects.filter(key=key).select_related("category").first()
        if not definition:
            continue
        permission = permissions.get(definition.category_id)
        if permission and not permission.can_edit:
            results.append({"key": key, "status": "forbidden"})
            continue

        owner = user if definition.scope == "user" else None
        value_obj = SettingValue.objects.filter(definition=definition, owner=owner).first()
        previous = value_obj.value if value_obj else definition.default_value

        value_obj, _ = SettingValue.objects.update_or_create(
            definition=definition,
            owner=owner,
            defaults={"value": value, "updated_by": user},
        )

        SettingHistory.objects.create(
            definition=definition,
            owner=owner,
            previous_value=previous,
            new_value=value,
            updated_by=user,
        )

        results.append({"key": key, "status": "updated", "value": value})

    return results


@transaction.atomic
def undo_last_change(user, key):
    definition = SettingDefinition.objects.filter(key=key).first()
    if not definition:
        return None
    owner = user if definition.scope == "user" else None
    history = (
        SettingHistory.objects.filter(definition=definition, owner=owner)
        .order_by("-created_at")
        .first()
    )
    if not history:
        return None

    SettingValue.objects.update_or_create(
        definition=definition,
        owner=owner,
        defaults={"value": history.previous_value, "updated_by": user},
    )

    SettingHistory.objects.create(
        definition=definition,
        owner=owner,
        previous_value=history.new_value,
        new_value=history.previous_value,
        updated_by=user,
    )

    return history.previous_value


def build_ai_hints(payload):
    hints = []
    settings_by_key = {}
    for category in payload.get("categories", []):
        for setting in category.get("settings", []):
            settings_by_key[setting["key"]] = setting.get("value")

    if not settings_by_key.get("company_gst"):
        hints.append("GST number is missing. Add GST to avoid tax compliance issues.")
    if not settings_by_key.get("invoice_series"):
        hints.append("Invoice series is empty. Set a unique series to prevent duplicates.")
    if settings_by_key.get("multi_currency") and settings_by_key.get("company_currency") == "INR":
        hints.append("Multi-currency is enabled. Consider configuring additional currencies.")
    if settings_by_key.get("thermal_mode") and settings_by_key.get("page_size") not in ["Thermal-80mm"]:
        hints.append("Thermal mode is ON but page size is not thermal. Switch page size to Thermal-80mm.")
    if settings_by_key.get("tax_inclusive_mode") == "inclusive" and settings_by_key.get("default_tax_mode") == "exclusive":
        hints.append("Tax mode mismatch. Align default tax mode with inclusive setting.")

    if not hints:
        hints.append("All critical settings look healthy. You're ready to go.")

    return hints


def get_status_cards(payload):
    settings_by_key = {}
    for category in payload.get("categories", []):
        for setting in category.get("settings", []):
            settings_by_key[setting["key"]] = setting.get("value")

    company_ready = bool(settings_by_key.get("company_name")) and bool(settings_by_key.get("company_gst"))
    tax_ready = bool(settings_by_key.get("gst_slabs")) or bool(settings_by_key.get("tax_categories"))
    printer_ready = bool(settings_by_key.get("invoice_printer")) or bool(settings_by_key.get("page_size"))
    whatsapp_ready = bool(settings_by_key.get("whatsapp_api_config"))

    return {
        "company_config_status": "Configured" if company_ready else "Missing",
        "tax_setup_status": "Configured" if tax_ready else "Missing",
        "printer_ready_status": "Ready" if printer_ready else "Not Ready",
        "whatsapp_connected_status": "Connected" if whatsapp_ready else "Not Connected",
    }
