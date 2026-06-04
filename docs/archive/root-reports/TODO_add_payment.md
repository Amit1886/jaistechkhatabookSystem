# TODO: Enhance add_payment.html Template

## Plan Overview
Transform the basic add_payment.html into an advanced, AI-powered, responsive template similar to add_party.html with multi-step wizard, automation, and modern UI.

## Information Gathered
- Payment model: invoice (FK), amount, method, reference, note, created_at
- Current template is basic; needs full overhaul
- Reference: add_party.html with multi-step wizard, AI features, responsive design

## Detailed Steps
- [x] Step 1: Invoice Selection & Amount (QR scan, auto-fill)
- [x] Step 2: Payment Details & Mode (method, reference, notes)
- [x] Step 3: Review & Confirm (summary, save options)
- [x] Add AI & Automation features
- [x] Implement responsive design for POS/PC/Mobile modes
- [x] Add keyboard shortcuts (F1-F5)
- [x] Include theme selector
- [x] Add step wizard indicator
- [x] Enhance UI with gradients, badges, cards
- [x] Add success popup
- [x] Include print/PDF/WhatsApp/SMS buttons
- [x] Test responsiveness and validation

## Dependent Files
- commerce/templates/commerce/add_payment.html (main edit)
- Reuse CSS/JS: add_order.css, add_order_enhanced.js

## Followup Steps
- Test across devices
- Verify form submission
- Add missing enhancements
