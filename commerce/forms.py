from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import inlineformset_factory
from decimal import Decimal
from .models import (
    Product,
    Warehouse,
    Order,
    OrderItem,
    Quotation,
    QuotationItem,
    Invoice,
    SalesVoucher,
    SalesVoucherItem,
    Coupon,
    Payment,
    ChatMessage,
)

# ---------------- Product Form ----------------
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "price",
            "stock",
            "min_stock",
            "sku",
            "description",
            "unit",
            "hsn_code",
            "gst_rate",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "price": forms.NumberInput(attrs={"class": "form-control"}),
            "unit": forms.TextInput(attrs={"class": "form-control"}),
            "sku": forms.TextInput(attrs={"class": "form-control"}),
            "hsn_code": forms.TextInput(attrs={"class": "form-control"}),
            "gst_rate": forms.NumberInput(attrs={"class": "form-control"}),
            "stock": forms.NumberInput(attrs={"class": "form-control"}),
            "min_stock": forms.NumberInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
        }

# ---------------- Warehouse Form ----------------
class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ['name', 'location', 'capacity']  # removed manager
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Warehouse name"}),
            "location": forms.TextInput(attrs={"class": "form-control", "placeholder": "Location"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
        }

# ---------------- Order Form ----------------
class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["party", "status", "notes", "assigned_to"]
        widgets = {
            "party": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "assigned_to": forms.Select(attrs={"class": "form-control"}),
        }


# ---------------- Order Item Form ----------------
class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ["product", "qty", "price"]
        widgets = {
            "product": forms.Select(attrs={"class": "form-control product-select"}),
            "qty": forms.NumberInput(attrs={"class": "form-control qty-input", "min": "1"}),
            "price": forms.NumberInput(attrs={"class": "form-control price-input", "min": "0", "step": "0.01"}),
        }


# ✅ Define Inline Formset
OrderItemFormSet = inlineformset_factory(
    Order, OrderItem,
    form=OrderItemForm,
    extra=1,  # show at least one item by default
    can_delete=True
)

# ---------------- Chat Message Form ----------------
class ChatMessageForm(forms.ModelForm):
    class Meta:
        model = ChatMessage
        fields = ["text", "attachment"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 2, "class": "form-control", "placeholder": "Type message..."}),
            "attachment": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

# ---------------- Invoice Form ----------------
class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["order", "status"]
        widgets = {
            "order": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

# ---------------- Coupon Form ----------------
class CouponForm(forms.ModelForm):
    valid_until = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"})
    )

    class Meta:
        model = Coupon
        fields = [
            "title", "code", "description", "coupon_type",
            "discount_type", "discount_value", "max_discount",
            "usage_limit", "per_user_limit", "min_order_amount",
            "valid_from", "valid_until", "is_active", "win_probability"
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "coupon_type": forms.Select(attrs={"class": "form-control"}),
            "discount_type": forms.Select(attrs={"class": "form-control"}),
            "discount_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "max_discount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "usage_limit": forms.NumberInput(attrs={"class": "form-control"}),
            "per_user_limit": forms.NumberInput(attrs={"class": "form-control"}),
            "min_order_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "valid_from": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "win_probability": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0", "max": "1"}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper()
        return code

# ---------------- Payment Form ----------------
class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["invoice", "amount", "method", "reference", "note"]
        widgets = {
            "invoice": forms.Select(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "method": forms.Select(attrs={"class": "form-control"}),
            "reference": forms.TextInput(attrs={"class": "form-control"}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class SalesVoucherForm(forms.ModelForm):
    class Meta:
        model = SalesVoucher
        fields = ["party", "date", "is_gst"]
        widgets = {
            "party": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "is_gst": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, user=None, order=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["party"].queryset = self.fields["party"].queryset.filter(owner=user).order_by("name")
        if order is not None and user is not None:
            self.fields["party"].queryset = self.fields["party"].queryset.filter(id=order.party_id, owner=user)


class SalesVoucherItemForm(forms.ModelForm):
    class Meta:
        model = SalesVoucherItem
        fields = ["product", "qty", "rate", "gst_rate", "warehouse", "source_order_item"]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "qty": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "0.01"}),
            "rate": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "0.01"}),
            "gst_rate": forms.Select(attrs={"class": "form-select"}),
            "warehouse": forms.Select(attrs={"class": "form-select"}),
            "source_order_item": forms.HiddenInput(),
        }

    def __init__(self, *args, user=None, order=None, **kwargs):
        self.order = order
        super().__init__(*args, **kwargs)

        if user is not None:
            # Allow NULL owner products for backwards compatibility.
            self.fields["product"].queryset = Product.objects.filter(models.Q(owner=user) | models.Q(owner__isnull=True)).order_by("name")

        if self.order is None:
            self.fields["source_order_item"].queryset = OrderItem.objects.none()
            self.remaining_qty = None
            return

        self.fields["source_order_item"].queryset = self.order.items.all()

        # Compute remaining qty for display.
        src_id = None
        try:
            src_id = (
                getattr(self.instance, "source_order_item_id", None)
                or self.initial.get("source_order_item")
            )
            if hasattr(src_id, "pk"):
                src_id = src_id.pk
            if src_id is not None:
                src_id = int(src_id)
        except Exception:
            src_id = None

        remaining = None
        if src_id and hasattr(self.order, "_items_by_id"):
            it = self.order._items_by_id.get(src_id)
            if it is not None:
                try:
                    remaining = Decimal(str(it.qty or 0)) - (it.invoiced_qty or Decimal("0.00"))
                except Exception:
                    remaining = None

                # Prevent changing product on order-linked rows by restricting choices.
                if getattr(it, "product_id", None):
                    self.fields["product"].queryset = Product.objects.filter(id=it.product_id)

        self.remaining_qty = remaining

    def clean(self):
        cleaned = super().clean()
        if self.order is None:
            return cleaned

        if self.cleaned_data.get("DELETE"):
            return cleaned

        src = cleaned.get("source_order_item")
        if not src:
            raise ValidationError("Invalid order item reference.")

        product = cleaned.get("product")
        if src.product_id and product and product.id != src.product_id:
            raise ValidationError("Product cannot be changed for an order-linked voucher line.")

        qty = cleaned.get("qty")
        if qty is None:
            raise ValidationError("Quantity is required.")

        try:
            qty_dec = Decimal(str(qty))
        except Exception:
            raise ValidationError("Invalid quantity.")

        if qty_dec <= Decimal("0.00"):
            raise ValidationError("Quantity must be greater than 0.")

        try:
            remaining = Decimal(str(src.qty or 0)) - (src.invoiced_qty or Decimal("0.00"))
        except Exception:
            remaining = None

        if remaining is not None and qty_dec > remaining:
            raise ValidationError(f"Cannot invoice more than remaining qty ({remaining}).")

        return cleaned


class BaseSalesVoucherItemFormSet(forms.BaseModelFormSet):
    def __init__(self, *args, order=None, **kwargs):
        self.order = order
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.order is None:
            return

        # Enforce summed qty per order item <= remaining.
        per_item = {}
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            src = form.cleaned_data.get("source_order_item")
            if not src:
                continue
            try:
                qty = Decimal(str(form.cleaned_data.get("qty") or "0"))
            except Exception:
                qty = Decimal("0.00")
            per_item[src.id] = per_item.get(src.id, Decimal("0.00")) + qty

        for src_id, qty_sum in per_item.items():
            src = self.order._items_by_id.get(int(src_id)) if hasattr(self.order, "_items_by_id") else None
            if not src:
                raise ValidationError("Invalid order item reference.")
            remaining = Decimal(str(src.qty or 0)) - (src.invoiced_qty or Decimal("0.00"))
            if qty_sum > remaining:
                raise ValidationError(
                    f"Cannot invoice more than remaining qty for item #{src_id} (remaining {remaining})."
                )


# ---------------- Quotations ----------------
class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ["party", "date", "valid_till", "warehouse", "remarks", "status"]
        widgets = {
            "party": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "valid_till": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "warehouse": forms.Select(attrs={"class": "form-select"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["party"].queryset = self.fields["party"].queryset.filter(owner=user).order_by("name")


class QuotationItemForm(forms.ModelForm):
    class Meta:
        model = QuotationItem
        fields = ["product", "qty", "rate", "discount", "tax", "warehouse", "total"]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "qty": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "1"}),
            "rate": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "0.01"}),
            "discount": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "0.01"}),
            "tax": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "0.01"}),
            "warehouse": forms.Select(attrs={"class": "form-select"}),
            "total": forms.NumberInput(attrs={"class": "form-control", "readonly": "readonly"}),
        }
