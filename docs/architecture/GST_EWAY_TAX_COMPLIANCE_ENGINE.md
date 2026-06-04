# GST, E-Way Bill, And Tax Compliance Engine

This engine is additive and tenant-scoped. It does not replace existing billing/commerce invoices yet; current invoice flows can gradually emit `gst_invoice_created` or create `GSTInvoice` records through the service layer.

## Official Rule Basis

CBIC Rule 138 requires e-way bill information before movement of goods when consignment value exceeds Rs. 50,000. FORM GST EWB-01 contains invoice/value/HSN/recipient and transport details including transporter document and vehicle number.

## Architecture

```text
Invoice Created
  -> GSTService.validate_invoice()
  -> GSTIN / PAN / HSN / duplicate checks
  -> GSTService.calculate_invoice()
  -> CGST + SGST for intra-state
  -> IGST for inter-state
  -> If total > 50000
       -> EWayBillRequest created
       -> UI asks transporter fields
       -> EWayBillService.prepare()
       -> eway_ready_payload generated
  -> Reports / audit / events
```

## Core Models

- `GSTTaxSlab`
- `HSNSACCode`
- `GSTParty`
- `PaymentQRProfile`
- `GSTInvoice`
- `GSTInvoiceLine`
- `EWayBillRequest`
- `TaxValidationIssue`
- `TaxAuditLog`
- `GSTReportSnapshot`

## E-Way Bill Required Fields

When invoice total exceeds Rs. 50,000, collect:

- transporter name
- transporter GSTIN
- vehicle number
- transport mode
- distance
- dispatch address
- dispatch pincode
- delivery address
- delivery pincode

## Invoice Formats

The invoice print context supports:

- A4 invoice
- thermal invoice
- transporter copy
- customer copy
- QR/payment block
- UPI payment URI
- bank account details
- IFSC
- payment link

## API

Base path:

`/api/v1/platform/tax/`

Important endpoints:

- `invoices/{id}/validate_gst/`
- `invoices/{id}/issue/`
- `invoices/{id}/payment_qr/`
- `invoices/{id}/print_context/`
- `eway-bills/{id}/prepare/`
- `eway-bills/{id}/mark_generated/`
- `reports/generate/`

## Reports

Supported report snapshots:

- GST sales register
- GST purchase register
- tax summary
- HSN summary
- GSTR-1
- GSTR-3B
- E-way bill report
- transporter report

## Integration Plan

Existing billing/commerce modules should integrate by:

1. Creating or mapping buyer/seller to `GSTParty`.
2. Creating `GSTInvoice` and `GSTInvoiceLine`.
3. Calling `GSTService.validate_invoice()`.
4. If e-way required, showing the e-way transport form.
5. Calling `EWayBillService.prepare()`.
6. Rendering invoice through `InvoicePrintService.render_context()`.
7. Posting accounting entries through the platform accounting service.

