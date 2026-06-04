from __future__ import annotations

from printer_config.models import PrintDocumentType


BASE_TEMPLATE_CSS = """
@page {
  size: auto;
  margin: 0;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 0;
  font-family: var(--font-family, Arial, sans-serif);
  font-size: var(--font-size, 12px);
  color: #111827;
  background: #fff;
}
body.print-theme-dark {
  color: #e5e7eb;
  background: #0f172a;
}
.print-document {
  width: 100%;
}
.sheet {
  width: 100%;
  margin: 0 auto;
  border: var(--border-size, 0) solid #d1d5db;
  padding: var(--padding-size, 0);
}
.doc-header {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 8px;
}
.doc-title {
  font-size: 18px;
  font-weight: 700;
}
.doc-subtitle {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  border: 1px solid transparent;
  white-space: nowrap;
}
.badge-paid { background: #dcfce7; color: #166534; border-color: #86efac; }
.badge-unpaid { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
.badge-pending { background: #ffedd5; color: #9a3412; border-color: #fed7aa; }
.badge-hold { background: #fef9c3; color: #854d0e; border-color: #fde68a; }
.badge-neutral { background: #e2e8f0; color: #0f172a; border-color: #cbd5e1; }
.top-right {
  text-align: right;
  display: grid;
  gap: 6px;
  justify-items: end;
}
.brand-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.logo {
  max-width: 130px;
  max-height: 70px;
  object-fit: contain;
}
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 10px;
}
.card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
}
.card-title {
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 6px;
}
.meta, .summary {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
}
.meta td, .summary td, .summary th {
  border: 1px solid #e5e7eb;
  padding: 6px 8px;
  vertical-align: top;
}
.summary th {
  text-align: left;
  background: #f8fafc;
}
.right {
  text-align: right;
}
.section-title {
  font-size: 13px;
  font-weight: 700;
  margin: 10px 0 6px 0;
}
.assets-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
}
.qr-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 10px;
}
.qr-card {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 8px;
  text-align: center;
}
.qr-card img { width: 92px; height: 92px; }
.qr-label { font-weight: 800; font-size: 11px; margin-top: 6px; }
.qr-sub { font-size: 10px; color: #475569; word-break: break-word; }
.small {
  font-size: 11px;
  color: #64748b;
}
.muted { color: #64748b; }
.divider {
  margin: 12px 0;
  border-top: 1px dashed #cbd5e1;
}
.btn {
  display: inline-block;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  padding: 6px 10px;
  border-radius: 10px;
  font-weight: 700;
  font-size: 11px;
  text-decoration: none;
  color: inherit;
}
.btn-primary {
  background: #0f766e;
  color: #fff;
  border-color: #0f766e;
}
.btn-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.page-break {
  page-break-before: always;
}
.items-wrap {
  page-break-inside: auto;
}
.items-wrap tr {
  page-break-inside: avoid;
}
.print-mode-pos .sheet,
.print-mode-mobile .sheet {
  padding: 0;
  border: 0;
}
.print-mode-pos .doc-title { font-size: 16px; }
.print-mode-pos .meta td, .print-mode-pos .summary td, .print-mode-pos .summary th { padding: 5px 6px; }
"""


INVOICE_TEMPLATE_HTML = """
<div class="sheet">
  {% if sections.header|default:True %}
  <div class="doc-header">
    <div>
      <div class="brand-row">
        <div>
          <div class="doc-title">
            {% if document_type == 'invoice' %}TAX INVOICE
            {% elif document_type == 'order_slip' %}ORDER SLIP
            {% elif document_type == 'cash_memo' %}CASH MEMO
            {% elif document_type == 'purchase_bill' %}PURCHASE BILL
            {% elif document_type == 'sales_bill' %}SALES BILL
            {% elif document_type == 'return_invoice' %}RETURN INVOICE
            {% elif document_type == 'transport_receipt' %}TRANSPORT RECEIPT
            {% elif document_type == 'delivery_challan' %}DELIVERY CHALLAN
            {% elif document_type == 'e_way_bill' %}E-WAY BILL
            {% elif document_type == 'credit_note' %}CREDIT NOTE
            {% elif document_type == 'debit_note' %}DEBIT NOTE
            {% else %}{{ document_type|default:"document"|upper }}{% endif %}
          </div>
          {% if header_text %}<div class="doc-subtitle">{{ header_text }}</div>{% endif %}
        </div>
        <div class="top-right">
          {% with st=document.status|default:""|lower %}
          <span class="badge
            {% if st == 'paid' %}badge-paid
            {% elif st == 'unpaid' %}badge-unpaid
            {% elif st == 'pending' %}badge-pending
            {% elif st == 'hold' %}badge-hold
            {% else %}badge-neutral{% endif %}
          ">
            {{ document.status|default:"-"|upper }}
          </span>
          {% endwith %}
          <div class="small muted">{{ generated_at }}</div>
        </div>
      </div>

      {% if config.company_info|default:True %}
      <div style="margin-top:8px;font-weight:800;">{{ company.name|default:"Company Name" }}</div>
      <div class="small">{{ company.address }}</div>
      <div class="small">{{ company.phone }} {% if company.email %}| {{ company.email }}{% endif %}</div>
      {% if company.tax_id %}<div class="small">GST/TAX: {{ company.tax_id }}</div>{% endif %}
      {% if company.website %}<div class="small">Web: {{ company.website }}</div>{% endif %}
      {% endif %}
    </div>
    <div>
      {% if company.logo_url %}
      <img class="logo" src="{{ company.logo_url }}" alt="logo">
      {% endif %}
    </div>
  </div>
  {% endif %}

  <table class="meta">
    <tr>
      <td><strong>No:</strong> {{ document.number }}</td>
      <td><strong>Date:</strong> {{ document.date }}</td>
      <td><strong>Due:</strong> {{ document.due_date|default:"-" }}</td>
    </tr>
    <tr>
      <td colspan="2"><strong>Customer:</strong> {{ customer.name }}</td>
      <td><strong>Phone:</strong> {{ customer.phone }}</td>
    </tr>
    {% if customer.address %}
    <tr>
      <td colspan="3"><strong>Address:</strong> {{ customer.address }}</td>
    </tr>
    {% endif %}
  </table>

  {% if sections.items|default:True and config.invoice_table|default:True %}
  <div class="section-title">Items / Services</div>
  <div class="items-wrap">
    <table class="summary">
      <thead>
        <tr>
          <th>#</th>
          <th>Item</th>
          <th>Qty</th>
          <th>Unit</th>
          <th class="right">Price</th>
          {% if config.table.show_discount_column|default:True %}<th class="right">Disc</th>{% endif %}
          {% if config.table.show_tax_column|default:True %}<th class="right">Tax</th>{% endif %}
          <th class="right">Amount</th>
        </tr>
      </thead>
      <tbody>
        {% for item in items %}
        <tr>
          <td>{{ forloop.counter }}</td>
          <td>
            <div style="font-weight:800;">{{ item.name }}</div>
            <div class="small">SKU: {{ item.sku }} {% if item.barcode %}| BC: {{ item.barcode }}{% endif %}</div>
          </td>
          <td>{{ item.qty }}</td>
          <td>{{ item.unit }}</td>
          <td class="right">{{ item.price }}</td>
          {% if config.table.show_discount_column|default:True %}<td class="right">{{ item.discount }}</td>{% endif %}
          {% if config.table.show_tax_column|default:True %}<td class="right">{{ item.tax }}</td>{% endif %}
          <td class="right"><strong>{{ item.amount }}</strong></td>
        </tr>
        {% empty %}
        <tr><td colspan="8" class="small">No items</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  {% if sections.totals|default:True %}
  <div class="section-title">Totals</div>
  <table class="meta">
    <tr><td>Subtotal</td><td class="right">{{ totals.subtotal }}</td></tr>
    <tr><td>Discount</td><td class="right">{{ totals.discount }}</td></tr>
    <tr><td>Tax</td><td class="right">{{ totals.tax }}</td></tr>
    <tr><td>Shipping</td><td class="right">{{ totals.shipping }}</td></tr>
    <tr><td><strong>Grand Total</strong></td><td class="right"><strong>{{ totals.grand_total }}</strong></td></tr>
    <tr><td>Paid</td><td class="right">{{ totals.paid }}</td></tr>
    <tr><td>Balance</td><td class="right">{{ totals.balance }}</td></tr>
  </table>
  {% endif %}

  {% if sections.assets|default:True %}
    {% if config.qr_code|default:True %}
    <div class="section-title">QR / Links</div>
    <div class="qr-grid">
      <div class="qr-card">
        {% if qr_image %}<img src="{{ qr_image }}" alt="doc-qr">{% endif %}
        <div class="qr-label">Document</div>
        <div class="qr-sub">{{ document.number }}</div>
      </div>
      {% if config.whatsapp_button|default:True and custom.whatsapp_qr_image %}
      <div class="qr-card">
        <img src="{{ custom.whatsapp_qr_image }}" alt="whatsapp-qr">
        <div class="qr-label">WhatsApp</div>
        <div class="qr-sub">{{ custom.whatsapp_link }}</div>
      </div>
      {% endif %}
      {% if config.map_button|default:True and custom.map_qr_image %}
      <div class="qr-card">
        <img src="{{ custom.map_qr_image }}" alt="map-qr">
        <div class="qr-label">Google Map</div>
        <div class="qr-sub">{{ custom.map_link }}</div>
      </div>
      {% endif %}
    </div>

    {% if config.social_links|default:True and custom.social_links %}
    <div class="divider"></div>
    <div class="card">
      <div class="card-title">Social Links</div>
      <table class="meta">
        {% for k, v in custom.social_links.items %}
        <tr>
          <td style="width:120px;"><strong>{{ k|title }}</strong></td>
          <td>{{ v }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
    {% endif %}

    <div class="divider"></div>
    <div class="grid-2">
      {% if config.bank_details|default:True and custom.bank_details %}
      <div class="card">
        <div class="card-title">Bank Details</div>
        <table class="meta">
          <tr><td>Account Name</td><td>{{ custom.bank_details.account_name }}</td></tr>
          <tr><td>Account No</td><td>{{ custom.bank_details.account_no }}</td></tr>
          <tr><td>IFSC</td><td>{{ custom.bank_details.ifsc }}</td></tr>
          <tr><td>UPI</td><td>{{ custom.bank_details.upi_id }}</td></tr>
        </table>
      </div>
      {% endif %}
      <div class="card">
        <div class="card-title">Quick Buttons</div>
        <div class="btn-row">
          {% if custom.website_link %}<a class="btn" href="{{ custom.website_link }}">Website</a>{% endif %}
          {% if config.whatsapp_button|default:True and custom.whatsapp_link %}<a class="btn btn-primary" href="{{ custom.whatsapp_link }}">WhatsApp</a>{% endif %}
          {% if config.map_button|default:True and custom.map_link %}<a class="btn" href="{{ custom.map_link }}">Open Map</a>{% endif %}
        </div>
        {% if barcode_image %}
        <div style="margin-top:10px;text-align:center;">
          <img src="{{ barcode_image }}" alt="barcode" style="max-width:260px;max-height:60px;">
          <div class="small">Barcode: {{ barcode_value }}</div>
        </div>
        {% endif %}
      </div>
    </div>

    {% if config.signature|default:True %}
    <div class="assets-row">
      <div></div>
      <div style="text-align:right;">
        {% if digital_signature_image %}
        <div><img src="{{ digital_signature_image }}" alt="signature" style="max-width:140px;max-height:70px;"></div>
        {% endif %}
        {% if stamp_image %}
        <div><img src="{{ stamp_image }}" alt="stamp" style="max-width:90px;max-height:90px;"></div>
        {% endif %}
      </div>
    </div>
    {% endif %}
    {% endif %}
  {% endif %}

  {% if sections.footer|default:True %}
    {% if config.terms_conditions|default:True and custom.terms_conditions %}
    <div class="card" style="margin-top:12px;">
      <div class="card-title">Terms &amp; Conditions</div>
      <div class="small">{{ custom.terms_conditions }}</div>
    </div>
    {% endif %}

    <div class="small" style="margin-top:12px;border-top:1px dashed #d1d5db;padding-top:8px;">
      {{ footer_text|default:company.name }}
    </div>
  {% endif %}
</div>
"""


RECEIPT_TEMPLATE_HTML = """
<div class="sheet">
  {% if sections.header|default:True %}
  <div class="doc-header">
    <div>
      <div class="brand-row">
        <div>
          <div class="doc-title">
            {% if document_type == 'receipt' %}RECEIPT
            {% elif document_type == 'payment_receipt' %}PAYMENT RECEIPT
            {% else %}{{ document_type|default:"receipt"|upper }}{% endif %}
          </div>
          {% if header_text %}<div class="doc-subtitle">{{ header_text }}</div>{% endif %}
        </div>
        <div class="top-right">
          {% with st=payment.status|default:document.status|default:""|lower %}
          <span class="badge
            {% if st == 'paid' or st == 'success' %}badge-paid
            {% elif st == 'unpaid' or st == 'failed' %}badge-unpaid
            {% elif st == 'pending' %}badge-pending
            {% elif st == 'hold' %}badge-hold
            {% else %}badge-neutral{% endif %}
          ">
            {{ payment.status|default:document.status|default:"-"|upper }}
          </span>
          {% endwith %}
          <div class="small muted">{{ generated_at }}</div>
        </div>
      </div>
      {% if config.company_info|default:True %}
      <div style="margin-top:8px;font-weight:800;">{{ company.name|default:"Company Name" }}</div>
      <div class="small">{{ company.address }}</div>
      <div class="small">{{ company.phone }} {% if company.email %}| {{ company.email }}{% endif %}</div>
      {% if company.tax_id %}<div class="small">GST/TAX: {{ company.tax_id }}</div>{% endif %}
      {% endif %}
    </div>
    <div>
      {% if company.logo_url %}<img class="logo" src="{{ company.logo_url }}" alt="logo">{% endif %}
    </div>
  </div>
  {% endif %}

  <div class="grid-2">
    <div class="card">
      <div class="card-title">Receipt Details</div>
      <table class="meta">
        <tr><td><strong>No</strong></td><td>{{ document.number }}</td></tr>
        <tr><td><strong>Date</strong></td><td>{{ document.date }}</td></tr>
        <tr><td><strong>Customer</strong></td><td>{{ customer.name }}</td></tr>
        <tr><td><strong>Phone</strong></td><td>{{ customer.phone }}</td></tr>
      </table>
    </div>
    <div class="card">
      <div class="card-title">Payment</div>
      <table class="meta">
        <tr><td><strong>Mode</strong></td><td>{{ payment.mode|default:"-" }}</td></tr>
        <tr><td><strong>Ref</strong></td><td>{{ payment.reference|default:"-" }}</td></tr>
        <tr><td><strong>Paid At</strong></td><td>{{ payment.paid_at|default:"-" }}</td></tr>
        <tr><td><strong>Amount</strong></td><td><strong>{{ totals.grand_total }}</strong></td></tr>
      </table>
    </div>
  </div>

  {% if sections.items|default:True and items %}
  <div class="section-title">Items</div>
  <div class="items-wrap">
    <table class="summary">
      <thead>
        <tr>
          <th>#</th>
          <th>Item</th>
          <th>Qty</th>
          <th class="right">Amount</th>
        </tr>
      </thead>
      <tbody>
        {% for item in items %}
        <tr>
          <td>{{ forloop.counter }}</td>
          <td>{{ item.name }}</td>
          <td>{{ item.qty }}</td>
          <td class="right"><strong>{{ item.amount }}</strong></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  {% if config.qr_code|default:True %}
  <div class="section-title">QR</div>
  <div class="qr-grid">
    <div class="qr-card">
      {% if qr_image %}<img src="{{ qr_image }}" alt="doc-qr">{% endif %}
      <div class="qr-label">Receipt</div>
      <div class="qr-sub">{{ document.number }}</div>
    </div>
    {% if config.whatsapp_button|default:True and custom.whatsapp_qr_image %}
    <div class="qr-card">
      <img src="{{ custom.whatsapp_qr_image }}" alt="whatsapp-qr">
      <div class="qr-label">WhatsApp</div>
      <div class="qr-sub">{{ custom.whatsapp_link }}</div>
    </div>
    {% endif %}
    {% if config.map_button|default:True and custom.map_qr_image %}
    <div class="qr-card">
      <img src="{{ custom.map_qr_image }}" alt="map-qr">
      <div class="qr-label">Google Map</div>
      <div class="qr-sub">{{ custom.map_link }}</div>
    </div>
    {% endif %}
  </div>
  {% endif %}

  {% if sections.footer|default:True %}
    <div class="small" style="margin-top:12px;border-top:1px dashed #d1d5db;padding-top:8px;">
      {{ footer_text|default:"Thank you" }}
    </div>
  {% endif %}
</div>
"""


def default_template_html(document_type: str) -> str:
    doc_type = (document_type or "").strip().lower()
    if doc_type in {PrintDocumentType.RECEIPT, PrintDocumentType.PAYMENT_RECEIPT}:
        return RECEIPT_TEMPLATE_HTML
    if doc_type in {
        PrintDocumentType.TRANSPORT_RECEIPT,
        PrintDocumentType.DELIVERY_CHALLAN,
        PrintDocumentType.E_WAY_BILL,
    }:
        return INVOICE_TEMPLATE_HTML.replace("Items / Services", "Consignment Items / Packages")
    if doc_type in {
        PrintDocumentType.CREDIT_NOTE,
        PrintDocumentType.DEBIT_NOTE,
    }:
        return INVOICE_TEMPLATE_HTML.replace("Totals", "Adjustment Summary")
    if doc_type == PrintDocumentType.REPORT_LAYOUT:
        return INVOICE_TEMPLATE_HTML.replace("Items / Services", "Report Rows")
    return INVOICE_TEMPLATE_HTML


def sample_template_config():
    return {
        "company_info": True,
        "billing_info": True,
        "shipping_info": True,
        "invoice_table": True,
        "bank_details": True,
        "qr_code": True,
        "social_links": True,
        "map_button": True,
        "whatsapp_button": True,
        "signature": True,
        "terms_conditions": True,
        "sections": {
            "header": True,
            "items": True,
            "totals": True,
            "assets": True,
            "footer": True,
        },
        "table": {
            "show_hsn": False,
            "show_barcode_column": False,
            "show_discount_column": True,
            "show_tax_column": True,
        },
        "branding": {
            "show_logo": True,
            "show_signature": True,
            "show_stamp": False,
        },
        "page_break": {
            "a4_multi_page": True,
            "rows_per_page": 20,
        },
    }
