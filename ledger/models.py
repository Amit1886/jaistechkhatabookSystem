from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class LedgerAccount(models.Model):
    """
    Ledger master (Chart of Accounts).

    Notes:
    - This is tenant-scoped by `owner` (user).
    - System ledgers (Sales, Cash, GST, etc.) are created per owner lazily by services.
    - Party ledgers are represented as LedgerAccounts with `party` set.
    """

    class AccountType(models.TextChoices):
        ASSET = "asset", "Asset"
        LIABILITY = "liability", "Liability"
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"
        EQUITY = "equity", "Equity"
        OTHER = "other", "Other"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gl_accounts",
        db_index=True,
    )

    code = models.CharField(
        max_length=64,
        help_text="Stable code (e.g. CASH, SALES, OUTPUT_GST_18, PARTY_123).",
    )
    name = models.CharField(max_length=200)
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.OTHER,
        db_index=True,
    )

    is_system = models.BooleanField(default=False, db_index=True)

    # Optional sub-ledger linkage
    party = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="gl_accounts",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "code"], name="uniq_gl_account_owner_code"),
            models.UniqueConstraint(
                fields=["owner", "party"],
                condition=models.Q(party__isnull=False),
                name="uniq_gl_account_owner_party",
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "account_type"], name="idx_glacc_owner_type"),
            models.Index(fields=["owner", "is_system"], name="idx_glacc_owner_system"),
        ]
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class LedgerTransaction(models.Model):
    """
    Voucher/header record used to group multiple LedgerEntry rows.

    Each source document (Invoice, Expense, Transaction, etc.) maps to ONE LedgerTransaction.
    All LedgerEntry rows under a transaction must be balanced (debit == credit).
    """

    class VoucherType(models.TextChoices):
        SALES_INVOICE = "sales_invoice", "Sales Invoice"
        PURCHASE_INVOICE = "purchase_invoice", "Purchase Invoice"
        EXPENSE = "expense", "Expense"
        RECEIPT = "receipt", "Receipt"
        PAYMENT = "payment", "Payment"
        CREDIT_NOTE = "credit_note", "Credit Note"
        DEBIT_NOTE = "debit_note", "Debit Note"
        JOURNAL = "journal", "Journal"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gl_transactions",
        db_index=True,
    )

    voucher_type = models.CharField(max_length=30, choices=VoucherType.choices, db_index=True)
    date = models.DateField(default=timezone.now, db_index=True)

    # Source tracking (Busy/Tally-like)
    reference_type = models.CharField(max_length=100, db_index=True)
    reference_id = models.PositiveBigIntegerField(db_index=True)
    reference_no = models.CharField(max_length=64, blank=True, default="")

    narration = models.TextField(blank=True, default="")

    total_debit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_credit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "voucher_type", "reference_type", "reference_id"],
                name="uniq_gl_txn_owner_source",
            ),
            models.CheckConstraint(
                check=models.Q(total_debit__gte=0) & models.Q(total_credit__gte=0),
                name="gl_txn_totals_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(total_debit=models.F("total_credit")),
                name="gl_txn_totals_balanced",
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "date"], name="idx_gltxn_owner_date"),
            models.Index(fields=["owner", "voucher_type", "date"], name="idx_gltxn_owner_type_date"),
            models.Index(fields=["owner", "reference_type", "reference_id"], name="idx_gltxn_owner_ref"),
        ]
        ordering = ["-date", "-id"]

    def __str__(self) -> str:
        return f"{self.voucher_type} {self.reference_no or self.reference_id} ({self.date})"


class Receipt(models.Model):
    """
    Universal printable receipt pointer for any source document.

    Notes:
    - Receipts are tenant-scoped by `owner`.
    - If a source document is posted to GL, `gl_transaction` points to the balanced LedgerTransaction.
    """

    class Kind(models.TextChoices):
        INVOICE = "invoice", "Invoice"
        ORDER = "order", "Order"
        VOUCHER = "voucher", "Voucher"
        PAYMENT = "payment", "Payment"
        CASH_PAID = "cash_paid", "Cash Paid"
        ONLINE_PAID = "online_paid", "Online Paid"
        PDC = "pdc", "PDC"
        ADVANCE = "advance", "Advance"
        REGULAR = "regular", "Regular"
        GST = "gst", "GST"
        NON_GST = "non_gst", "Non-GST"
        NOT_APPLICABLE = "not_applicable", "Not Applicable"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="receipts",
        db_index=True,
    )

    kind = models.CharField(max_length=30, choices=Kind.choices, default=Kind.NOT_APPLICABLE, db_index=True)

    reference_type = models.CharField(max_length=100, db_index=True)
    reference_id = models.PositiveBigIntegerField(db_index=True)
    voucher_type = models.CharField(max_length=30, blank=True, default="", db_index=True)

    receipt_no = models.CharField(max_length=64, blank=True, default="")
    gst_enabled = models.BooleanField(default=False, db_index=True)

    gl_transaction = models.ForeignKey(
        "ledger.LedgerTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipts",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "reference_type", "reference_id", "voucher_type"],
                name="uniq_receipt_owner_source",
            )
        ]
        indexes = [
            models.Index(fields=["owner", "kind", "created_at"], name="idx_receipt_owner_kind_dt"),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return self.receipt_no or f"{self.reference_type}:{self.reference_id}"


class LedgerEntry(models.Model):
    """
    General Ledger line (double-entry).

    Exactly one of `debit` or `credit` must be > 0.
    """

    transaction = models.ForeignKey(
        LedgerTransaction,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    account = models.ForeignKey(
        LedgerAccount,
        on_delete=models.PROTECT,
        related_name="entries",
    )

    party = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="gl_entries",
        help_text="Optional party sub-ledger for this line.",
    )

    line_no = models.PositiveSmallIntegerField(default=1)
    description = models.CharField(max_length=255, blank=True, default="")

    debit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["transaction", "line_no"], name="uniq_gl_entry_txn_line"),
            models.CheckConstraint(
                check=models.Q(debit__gte=0) & models.Q(credit__gte=0),
                name="gl_entry_non_negative",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(debit__gt=0, credit=0) |
                    models.Q(credit__gt=0, debit=0)
                ),
                name="gl_entry_one_side_only",
            ),
        ]
        indexes = [
            models.Index(fields=["transaction", "line_no"], name="idx_glent_txn_line"),
            models.Index(fields=["account"], name="idx_glent_account"),
            models.Index(fields=["party"], name="idx_glent_party"),
        ]
        ordering = ["transaction_id", "line_no", "id"]

    def __str__(self) -> str:
        amount = self.debit if self.debit > 0 else self.credit
        side = "DR" if self.debit > 0 else "CR"
        return f"{self.transaction_id} {self.account.code} {side} {amount}"


class StockLedger(models.Model):
    """
    Stock movement ledger (warehouse-wise and product-wise).

    This is an append-only audit log, but we sync (delete+recreate) per source document to
    keep it consistent with edits while preventing duplicates.

    Rules:
    - Exactly one of `quantity_in` / `quantity_out` must be > 0.
    - Movements reference a source document via (reference_type, reference_id, reference_line_id).
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stock_ledger_entries",
        db_index=True,
    )

    class Movement(models.TextChoices):
        IN = "in", "In"
        OUT = "out", "Out"

    date = models.DateField(default=timezone.now, db_index=True)
    product = models.ForeignKey("commerce.Product", on_delete=models.PROTECT, related_name="stock_ledger_entries")
    warehouse = models.ForeignKey(
        "commerce.Warehouse",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_ledger_entries",
        help_text="Nullable until warehouse is captured in source flows.",
    )

    movement = models.CharField(max_length=3, choices=Movement.choices, db_index=True)

    quantity_in = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    quantity_out = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    reference_type = models.CharField(max_length=100, db_index=True)
    reference_id = models.PositiveBigIntegerField(db_index=True)
    reference_line_id = models.PositiveBigIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "reference_type", "reference_id", "reference_line_id", "product", "movement"],
                name="uniq_stock_ledger_ref_line_product",
            ),
            models.CheckConstraint(
                check=models.Q(quantity_in__gte=0) & models.Q(quantity_out__gte=0),
                name="stock_ledger_non_negative",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(quantity_in__gt=0, quantity_out=0) |
                    models.Q(quantity_out__gt=0, quantity_in=0)
                ),
                name="stock_ledger_one_side_only",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(movement="in", quantity_in__gt=0, quantity_out=0) |
                    models.Q(movement="out", quantity_out__gt=0, quantity_in=0)
                ),
                name="stock_ledger_movement_match",
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "date"], name="idx_stock_owner_date"),
            models.Index(fields=["owner", "product", "date"], name="idx_stock_owner_prod_date"),
            models.Index(fields=["owner", "warehouse", "date"], name="idx_stock_owner_wh_date"),
            models.Index(fields=["owner", "reference_type", "reference_id"], name="idx_stock_owner_ref"),
        ]
        ordering = ["-date", "-id"]

    def __str__(self) -> str:
        qty = self.quantity_in if self.quantity_in > 0 else self.quantity_out
        side = self.movement.upper()
        return f"{self.product_id} {side} {qty} ({self.date})"


class StockTransfer(models.Model):
    """
    Stock transfer between warehouses (foundation).

    Posting to StockLedger is handled via signals when status becomes POSTED.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stock_transfers",
        db_index=True,
    )
    date = models.DateField(default=timezone.now, db_index=True)
    from_warehouse = models.ForeignKey("commerce.Warehouse", on_delete=models.PROTECT, related_name="stock_transfers_out")
    to_warehouse = models.ForeignKey("commerce.Warehouse", on_delete=models.PROTECT, related_name="stock_transfers_in")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner", "date"], name="idx_trf_owner_date"),
            models.Index(fields=["owner", "status", "date"], name="idx_trf_owner_status_date"),
        ]
        ordering = ["-date", "-id"]

    def __str__(self) -> str:
        return f"Transfer {self.id} {self.from_warehouse_id}->{self.to_warehouse_id} ({self.status})"


class StockTransferItem(models.Model):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("commerce.Product", on_delete=models.PROTECT, related_name="stock_transfer_items")
    quantity = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        indexes = [models.Index(fields=["transfer", "product"], name="idx_trfi_trf_prod")]

    def __str__(self) -> str:
        return f"{self.transfer_id} - {self.product_id} x {self.quantity}"


class JournalVoucher(models.Model):
    """
    Manual journal voucher (foundation).

    Posting to LedgerTransaction/LedgerEntry is handled via signals when status is POSTED.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="journal_vouchers",
        db_index=True,
    )
    date = models.DateField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    narration = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner", "date"], name="idx_jv_owner_date"),
            models.Index(fields=["owner", "status", "date"], name="idx_jv_owner_status_date"),
        ]
        ordering = ["-date", "-id"]

    def __str__(self) -> str:
        return f"Journal {self.id} ({self.status})"


class JournalVoucherLine(models.Model):
    voucher = models.ForeignKey(JournalVoucher, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(LedgerAccount, on_delete=models.PROTECT, related_name="journal_lines")
    party = models.ForeignKey("khataapp.Party", on_delete=models.PROTECT, null=True, blank=True, related_name="journal_lines")

    description = models.CharField(max_length=255, blank=True, default="")
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(debit__gte=0) & models.Q(credit__gte=0),
                name="journal_line_non_negative",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(debit__gt=0, credit=0) |
                    models.Q(credit__gt=0, debit=0)
                ),
                name="journal_line_one_side_only",
            ),
        ]
        indexes = [models.Index(fields=["voucher", "account"], name="idx_jvl_voucher_account")]
        ordering = ["id"]

    def __str__(self) -> str:
        amount = self.debit if self.debit > 0 else self.credit
        side = "DR" if self.debit > 0 else "CR"
        return f"{self.voucher_id} {self.account.code} {side} {amount}"


class ReturnNote(models.Model):
    """
    Credit/Debit note issued against an invoice (returns / adjustments).

    - CREDIT note: Sales return (stock IN, reverse sales + output GST).
    - DEBIT note: Purchase return (stock OUT, reverse purchase + input GST).
    """

    class NoteType(models.TextChoices):
        CREDIT = "credit", "Credit Note"
        DEBIT = "debit", "Debit Note"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="return_notes",
        db_index=True,
    )
    invoice = models.ForeignKey("commerce.Invoice", on_delete=models.PROTECT, related_name="return_notes")
    note_type = models.CharField(max_length=10, choices=NoteType.choices, db_index=True)
    date = models.DateField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    narration = models.TextField(blank=True, default="")

    taxable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner", "note_type", "date"], name="idx_rn_owner_type_date"),
            models.Index(fields=["owner", "status", "date"], name="idx_rn_owner_status_date"),
        ]
        ordering = ["-date", "-id"]

    def compute_totals(self) -> None:
        total_taxable = Decimal("0.00")
        for it in self.items.all():
            qty = Decimal(str(getattr(it, "quantity", 0) or 0))
            rate = Decimal(str(getattr(it, "rate", 0) or 0))
            if qty > 0 and rate >= 0:
                total_taxable += (qty * rate)

        tax_percent = Decimal("0.00")
        try:
            order = getattr(self.invoice, "order", None)
            tax_percent = Decimal(str(getattr(order, "tax_percent", 0) or 0))
        except Exception:
            tax_percent = Decimal("0.00")

        gst_type = (getattr(self.invoice, "gst_type", "") or "").upper()
        total_tax = Decimal("0.00")
        if gst_type == "GST" and tax_percent > 0:
            total_tax = (total_taxable * tax_percent) / Decimal("100")

        self.taxable_amount = total_taxable.quantize(Decimal("0.01"))
        self.tax_amount = total_tax.quantize(Decimal("0.01"))
        self.total_amount = (self.taxable_amount + self.tax_amount).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                self.compute_totals()
            except Exception:
                pass
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.note_type.upper()} #{self.id} ({self.status})"


class ReturnNoteItem(models.Model):
    note = models.ForeignKey(ReturnNote, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("commerce.Product", on_delete=models.PROTECT, related_name="return_note_items")
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    rate = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        indexes = [
            models.Index(fields=["note", "product"], name="idx_rni_note_product"),
        ]
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.note_id} - {self.product_id} x {self.quantity}"
