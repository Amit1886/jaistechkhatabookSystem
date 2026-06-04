from __future__ import annotations

import base64
import logging
import re
from io import BytesIO
from typing import Any
from urllib.parse import quote_plus

from django.template import Context, Template, TemplateSyntaxError

from printer_config.models import PrintMode, PrintPaperSize
from printer_config.services.placeholder_catalog import flatten_placeholder_keys
from printer_config.services.sample_templates import BASE_TEMPLATE_CSS, default_template_html, sample_template_config

logger = logging.getLogger(__name__)

try:  # Optional dependency
    import qrcode

    QR_AVAILABLE = True
except Exception:  # pragma: no cover
    QR_AVAILABLE = False

try:  # Optional dependency
    from barcode import Code128
    from barcode.writer import ImageWriter

    BARCODE_AVAILABLE = True
except Exception:  # pragma: no cover
    BARCODE_AVAILABLE = False


def _file_to_data_uri(file_field) -> str:
    if not file_field:
        return ""
    try:
        with file_field.open("rb") as handle:
            raw = handle.read()
        encoded = base64.b64encode(raw).decode("utf-8")
        mime = "image/png"
        name = str(getattr(file_field, "name", "")).lower()
        if name.endswith(".jpg") or name.endswith(".jpeg"):
            mime = "image/jpeg"
        elif name.endswith(".svg"):
            mime = "image/svg+xml"
        return f"data:{mime};base64,{encoded}"
    except Exception:
        return ""


def _generate_qr_data_uri(value: str) -> str:
    if not value or not QR_AVAILABLE:
        return ""
    try:
        qr = qrcode.QRCode(box_size=3, border=1)
        qr.add_data(str(value))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        out = BytesIO()
        img.save(out, format="PNG")
        encoded = base64.b64encode(out.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
    except Exception:
        return ""


def _generate_barcode_data_uri(value: str) -> str:
    if not value or not BARCODE_AVAILABLE:
        return ""
    try:
        out = BytesIO()
        barcode = Code128(str(value), writer=ImageWriter())
        barcode.write(out)
        encoded = base64.b64encode(out.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
    except Exception:
        return ""


def _resolve_size(paper_size: str, width_value: Any, height_value: Any, unit: str):
    if width_value and height_value:
        return f"{width_value}{unit} {height_value}{unit}"
    size_map = {
        PrintPaperSize.A4: "210mm 297mm",
        PrintPaperSize.A5: "148mm 210mm",
        PrintPaperSize.POS_58: "58mm auto",
        PrintPaperSize.POS_80: "80mm auto",
        PrintPaperSize.MOBILE: "390px auto",
        PrintPaperSize.TABLET: "820px auto",
        PrintPaperSize.DESKTOP: "1200px auto",
    }
    return size_map.get(paper_size, "auto")


def _page_css(config: dict, print_mode: str) -> str:
    paper_size = config.get("paper_size", PrintPaperSize.A4)
    unit = config.get("size_unit", "mm")
    size_rule = _resolve_size(
        paper_size=paper_size,
        width_value=config.get("width_value"),
        height_value=config.get("height_value"),
        unit=unit,
    )
    margin_top = config.get("margin_top", 0)
    margin_right = config.get("margin_right", 0)
    margin_bottom = config.get("margin_bottom", 0)
    margin_left = config.get("margin_left", 0)
    padding_value = config.get("padding_value", 0)
    border_value = config.get("border_value", 0)
    font_family = config.get("font_family") or "Arial, sans-serif"
    font_size = int(config.get("font_size", 12))
    text_align = config.get("text_align", "left")

    mode_scale = {
        PrintMode.POS: "1.0",
        PrintMode.MOBILE: "0.96",
        PrintMode.TABLET: "1.0",
        PrintMode.DESKTOP: "1.0",
    }.get(print_mode, "1.0")

    return f"""
@page {{
  size: {size_rule};
  margin: {margin_top}{unit} {margin_right}{unit} {margin_bottom}{unit} {margin_left}{unit};
}}
:root {{
  --font-family: {font_family};
  --font-size: {font_size}px;
  --padding-size: {padding_value}{unit};
  --border-size: {border_value}{unit};
}}
body {{
  text-align: {text_align};
  transform: scale({mode_scale});
  transform-origin: top left;
}}
"""


def _effective_template(template_obj=None, user_template=None, document_type: str = ""):
    html = default_template_html(document_type)
    css = ""
    cfg = sample_template_config()

    if template_obj:
        if template_obj.html_template:
            html = template_obj.html_template
        if template_obj.css_template:
            css = f"{css}\n{template_obj.css_template}"
        cfg = {
            **cfg,
            "paper_size": template_obj.paper_size,
            "width_value": template_obj.width_value,
            "height_value": template_obj.height_value,
            "size_unit": template_obj.size_unit,
            "margin_top": template_obj.margin_top,
            "margin_right": template_obj.margin_right,
            "margin_bottom": template_obj.margin_bottom,
            "margin_left": template_obj.margin_left,
            "padding_value": template_obj.padding_value,
            "border_value": template_obj.border_value,
            "font_family": template_obj.font_family,
            "font_size": template_obj.font_size,
            "text_align": template_obj.text_align,
            "allow_dark_mode": template_obj.allow_dark_mode,
        }
        if template_obj.json_config:
            cfg.update(template_obj.json_config)

    if user_template:
        if user_template.custom_html:
            html = user_template.custom_html
        if user_template.custom_css:
            css = f"{css}\n{user_template.custom_css}"
        cfg.update(
            {
                "paper_size": user_template.paper_size,
                "width_value": user_template.width_value,
                "height_value": user_template.height_value,
                "size_unit": user_template.size_unit,
                "margin_top": user_template.margin_top,
                "margin_right": user_template.margin_right,
                "margin_bottom": user_template.margin_bottom,
                "margin_left": user_template.margin_left,
                "padding_value": user_template.padding_value,
                "border_value": user_template.border_value,
                "font_family": user_template.font_family or cfg.get("font_family"),
                "font_size": user_template.font_size or cfg.get("font_size"),
                "theme_mode": user_template.theme_mode,
            }
        )
    return html, css, cfg


def render_template_payload(
    *,
    document_type: str,
    context: dict,
    template_obj=None,
    user_template=None,
    print_mode: str = PrintMode.DESKTOP,
):
    html_template, css_template, config = _effective_template(
        template_obj=template_obj,
        user_template=user_template,
        document_type=document_type,
    )

    sections = {}
    if template_obj and template_obj.enabled_sections:
        sections.update(template_obj.enabled_sections)
    if user_template and user_template.section_visibility:
        sections.update(user_template.section_visibility)
    if not sections and isinstance(config.get("sections"), dict):
        sections = dict(config.get("sections") or {})
    if not sections:
        sections = {"header": True, "items": True, "totals": True, "assets": True, "footer": True}

    payload = dict(context)
    payload.setdefault("document_type", document_type)
    payload.setdefault("sections", sections)
    payload.setdefault("print_mode", print_mode)
    payload.setdefault("theme_mode", config.get("theme_mode", "light"))
    payload.setdefault("config", config)
    payload.setdefault("header_text", "")
    payload.setdefault("footer_text", "")
    payload.setdefault("qr_value", payload.get("document", {}).get("number", ""))
    payload.setdefault("barcode_value", payload.get("document", {}).get("number", ""))

    if user_template:
        payload["header_text"] = payload.get("header_text") or user_template.header_text
        payload["footer_text"] = payload.get("footer_text") or user_template.footer_text
        payload["theme_mode"] = user_template.theme_mode
        payload["company"] = dict(payload.get("company", {}))
        payload["company"]["name"] = user_template.company_name or payload["company"].get("name", "")
        payload["company"]["address"] = user_template.company_address or payload["company"].get("address", "")
        payload["company"]["phone"] = user_template.company_phone or payload["company"].get("phone", "")
        payload["company"]["email"] = user_template.company_email or payload["company"].get("email", "")
        payload["company"]["tax_id"] = user_template.company_tax_id or payload["company"].get("tax_id", "")
        payload["company"]["website"] = user_template.company_website or payload["company"].get("website", "")
        if user_template.logo:
            payload["company"]["logo_url"] = _file_to_data_uri(user_template.logo)
        payload.setdefault("custom", {})
        payload["custom"].update(user_template.custom_fields or {})

        signature_enabled = bool(user_template.show_digital_signature and user_template.signature_image)
        stamp_enabled = bool(user_template.show_stamp and user_template.stamp_image)
        payload["digital_signature_image"] = _file_to_data_uri(user_template.signature_image) if signature_enabled else ""
        payload["stamp_image"] = _file_to_data_uri(user_template.stamp_image) if stamp_enabled else ""

        if user_template.qr_enabled:
            payload["qr_image"] = _generate_qr_data_uri(str(payload.get("qr_value", "")))
        if user_template.barcode_enabled:
            payload["barcode_image"] = _generate_barcode_data_uri(str(payload.get("barcode_value", "")))
    else:
        payload.setdefault("digital_signature_image", "")
        payload.setdefault("stamp_image", "")
        payload.setdefault("qr_image", _generate_qr_data_uri(str(payload.get("qr_value", ""))))
        payload.setdefault("barcode_image", _generate_barcode_data_uri(str(payload.get("barcode_value", ""))))

    # ---- Optional extra QR/link helpers for templates ----
    custom = payload.get("custom")
    if not isinstance(custom, dict):
        custom = {}
        payload["custom"] = custom

    def _ensure_http_url(value: Any) -> str:
        if value in (None, ""):
            return ""
        s = str(value).strip()
        if not s:
            return ""
        if s.startswith("http://") or s.startswith("https://"):
            return s
        return f"https://{s}"

    # Website QR (fallback from company.website)
    website_link = _ensure_http_url(custom.get("website_link") or payload.get("company", {}).get("website", ""))
    if website_link:
        custom.setdefault("website_link", website_link)
        custom.setdefault("website_qr_image", _generate_qr_data_uri(website_link))

    # WhatsApp QR (fallback from custom.whatsapp_* or company.phone)
    wa_raw = custom.get("whatsapp_number") or custom.get("whatsapp_no") or custom.get("whatsapp") or payload.get("company", {}).get("phone", "")
    wa_digits = re.sub(r"\\D", "", str(wa_raw or ""))
    if wa_digits:
        if len(wa_digits) == 10 and not wa_digits.startswith("91"):
            wa_digits = f"91{wa_digits}"
        wa_link = f"https://wa.me/{wa_digits}"
        custom.setdefault("whatsapp_link", wa_link)
        custom.setdefault("whatsapp_qr_image", _generate_qr_data_uri(wa_link))

    # Google Maps QR (map_link or derived from map_query/company.address)
    map_link = custom.get("map_link") or custom.get("google_map_link")
    if not map_link:
        query = custom.get("map_query") or payload.get("company", {}).get("address", "")
        if query:
            map_link = f"https://www.google.com/maps/search/?api=1&query={quote_plus(str(query))}"
    map_link = _ensure_http_url(map_link)
    if map_link:
        custom.setdefault("map_link", map_link)
        custom.setdefault("map_qr_image", _generate_qr_data_uri(map_link))

    # Social links + optional QR set (supports dict `social_links` or individual `*_link` keys)
    social_links = custom.get("social_links")
    if not isinstance(social_links, dict):
        social_links = {}
    for key in ("instagram", "facebook", "youtube", "twitter", "linkedin"):
        val = custom.get(f"{key}_link") or social_links.get(key)
        val = _ensure_http_url(val)
        if val:
            social_links[key] = val
    if social_links:
        custom["social_links"] = social_links
        if "social_qr_images" not in custom:
            custom["social_qr_images"] = {k: _generate_qr_data_uri(v) for k, v in social_links.items() if v}

    page_css = _page_css(config=config, print_mode=print_mode)
    final_css = f"{BASE_TEMPLATE_CSS}\n{page_css}\n{css_template}"

    try:
        rendered_fragment = Template(html_template).render(Context(payload))
    except TemplateSyntaxError as exc:
        logger.warning("Print template syntax error: %s", exc)
        rendered_fragment = (
            "<div style='padding:8px;border:1px solid #fecaca;color:#991b1b;'>"
            "Template syntax error. Please fix template HTML."
            "</div>"
        )

    final_html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{document_type}</title>
  <style>{final_css}</style>
</head>
<body class="print-theme-{'dark' if payload.get('theme_mode') == 'dark' else 'light'} print-mode-{print_mode}">
  <div class="print-document">{rendered_fragment}</div>
</body>
</html>
"""
    return {
        "html": final_html,
        "css": final_css,
        "config": config,
        "placeholders": flatten_placeholder_keys(),
        "payload": payload,
    }
