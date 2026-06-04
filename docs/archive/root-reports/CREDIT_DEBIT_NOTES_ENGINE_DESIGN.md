# CREDIT NOTE & DEBIT NOTE ENGINE DESIGN DOCUMENT

## SECTION 1 — CONCEPT & ACCOUNTING FOUNDATION

### What is Credit Note
A Credit Note is a document issued by a seller to a buyer, reducing the amount owed by the buyer. It acts as a negative invoice that adjusts the original transaction amount downward.

**Legal Requirement**: Mandatory under GST law (Section 34 of CGST Act, 2017) for any reduction in taxable value or tax liability after invoice issuance.

### What is Debit Note
A Debit Note is issued by a buyer to a seller, increasing the amount owed to the seller. It acts as a positive adjustment to the original invoice amount.

**Legal Requirement**: Required under GST law (Section 34 of CGST Act, 2017) when taxable value or tax liability increases after invoice issuance.

### Why They Are Legally Required
- **GST Compliance**: All adjustments to taxable supplies must be documented
- **Audit Trail**: Maintains complete transaction history for tax authorities
- **Input Tax Credit**: Proper documentation ensures ITC eligibility
- **Financial Reporting**: Accurate reflection of true business transactions

### Difference Between Sales vs Purchase Notes

| Aspect | Sales Credit Note | Sales Debit Note | Purchase Credit Note | Purchase Debit Note |
|--------|------------------|------------------|---------------------|-------------------|
| Issuer | Seller | Seller | Buyer | Buyer |
| Recipient | Buyer | Buyer | Seller | Seller |
| Impact on Seller | Reduces Receivable | Increases Receivable | Reduces Payable | Increases Payable |
| Impact on Buyer | Reduces Payable | Increases Payable | Reduces Receivable | Increases Receivable |

### GST Impact of Each

**Sales Credit Note**:
- Reduces seller's GST liability
- Buyer can claim ITC reduction
- Must be reported in GSTR-1 (outward supplies)

**Sales Debit Note**:
- Increases seller's GST liability
- Buyer gets additional ITC
- Must be reported in GSTR-1

**Purchase Credit Note**:
- Reduces buyer's ITC eligibility
- Seller reduces outward GST liability
- Reported in GSTR-2 (inward supplies)

**Purchase Debit Note**:
- Increases buyer's ITC
- Seller increases GST liability
- Reported in GSTR-2

### Ledger Impact of Each

**Sales Credit Note**:
```
Dr. Customer A/c (Receivable)    XXX
    Cr. Sales Account                 XXX
    Cr. Output GST Account            XXX
```

**Sales Debit Note**:
```
Dr. Sales Account                    XXX
Dr. Output GST Account               XXX
    Cr. Customer A/c (Receivable)     XXX
