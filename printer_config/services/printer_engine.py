from django.template import Context, Template

from printer_config.models import PrinterTestLog
from printer_config.services.access_control import allowed_templates_queryset, select_default_template_for_user
from printer_config.services.context_builder import build_document_context
from printer_config.services.template_renderer import render_template_payload

DEFAULT_TEMPLATES = {
    "pos_invoice": "<h3>POS Invoice</h3><p>Order: {{ order_number }}</p><p>Total: {{ total_amount }}</p>",
    "retail_invoice": "<h3>Retail Invoice</h3><p>Order: {{ order_number }}</p>",
    "wholesale_invoice": "<h3>Wholesale Invoice</h3><p>Order: {{ order_number }}</p>",
    "credit_invoice": "<h3>Credit Invoice</h3><p>Order: {{ order_number }}</p>",
    "return_bill": "<h3>Return Bill</h3><p>Order: {{ order_number }}</p>",
}


def render_invoice_template(printer, payload: dict):
    data = payload or {}
    nested_payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}

    merged = dict(nested_payload)
    for key in ("document_type", "template_id", "user_template_id", "print_mode", "source_model", "source_id"):
        if key in data and key not in merged:
            merged[key] = data[key]

    document_type = (merged.get("document_type") or "").strip().lower()
    template_id = merged.get("template_id")
    user_template_id = merged.get("user_template_id")

    rich_keys = {"document", "items", "totals", "source_model", "source_id"}
    is_rich_payload = any(k in merged and merged.get(k) not in (None, "", {}, []) for k in rich_keys)

    if document_type or template_id or user_template_id or is_rich_payload:
        from printer_config.models import PrintDocumentType, PrintMode, UserPrintTemplate

        doc_type = document_type or PrintDocumentType.INVOICE
        print_mode = merged.get("print_mode") or PrintMode.DESKTOP
        source_model = merged.get("source_model", "")
        source_id = merged.get("source_id")

        user_template = None
        template_obj = None

        if user_template_id:
            user_template = (
                UserPrintTemplate.objects.filter(
                    pk=user_template_id,
                    user=printer.user,
                    is_active=True,
                )
                .select_related("template")
                .first()
            )
            if user_template:
                template_obj = user_template.template
                doc_type = user_template.document_type
                print_mode = user_template.print_mode or print_mode

        if template_id and not template_obj:
            template_obj = allowed_templates_queryset(printer.user).filter(pk=template_id).first()
            if template_obj:
                doc_type = template_obj.document_type

        if not template_obj and not user_template:
            template_obj = select_default_template_for_user(printer.user, document_type=doc_type)

        selection_keys = {"document_type", "template_id", "user_template_id", "print_mode", "source_model", "source_id"}
        context_payload = {k: v for k, v in merged.items() if k not in selection_keys}
        context = build_document_context(
            document_type=doc_type,
            source_model=source_model,
            source_id=source_id,
            payload=context_payload,
            user=printer.user,
        )
        rendered = render_template_payload(
            document_type=doc_type,
            context=context,
            template_obj=template_obj,
            user_template=user_template,
            print_mode=print_mode,
        )
        return rendered["html"]

    template_string = printer.template_html or DEFAULT_TEMPLATES.get(
        data.get("invoice_type", "pos_invoice"),
        DEFAULT_TEMPLATES["pos_invoice"],
    )
    return Template(template_string).render(Context(data))


def test_print(printer):
    PrinterTestLog.objects.create(printer=printer, result="success", message="Test print simulated")
    return "success"
