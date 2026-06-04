from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from ledger.models import (
    JournalVoucher,
    JournalVoucherLine,
    ReturnNote,
    ReturnNoteItem,
    StockTransfer,
    StockTransferItem,
)


class StockTransferForm(forms.ModelForm):
    class Meta:
        model = StockTransfer
        fields = ["date", "from_warehouse", "to_warehouse", "notes", "status"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "from_warehouse": forms.Select(attrs={"class": "form-select"}),
            "to_warehouse": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Notes (optional)"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned = super().clean()
        from_wh = cleaned.get("from_warehouse")
        to_wh = cleaned.get("to_warehouse")
        if from_wh and to_wh and from_wh == to_wh:
            raise forms.ValidationError("From and To warehouse cannot be the same.")
        return cleaned


class StockTransferItemForm(forms.ModelForm):
    class Meta:
        model = StockTransferItem
        fields = ["product", "quantity"]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control text-end", "step": "0.01", "min": "0"}),
        }

    def clean_quantity(self):
        q = self.cleaned_data.get("quantity")
        if q is None:
            return q
        if q <= 0:
            raise forms.ValidationError("Quantity must be greater than 0.")
        return q


StockTransferItemFormSet = inlineformset_factory(
    StockTransfer,
    StockTransferItem,
    form=StockTransferItemForm,
    extra=1,
    can_delete=True,
)


class JournalVoucherForm(forms.ModelForm):
    class Meta:
        model = JournalVoucher
        fields = ["date", "narration", "status"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "narration": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Narration"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }


class JournalVoucherLineForm(forms.ModelForm):
    class Meta:
        model = JournalVoucherLine
        fields = ["account", "party", "description", "debit", "credit"]
        widgets = {
            "account": forms.Select(attrs={"class": "form-select"}),
            "party": forms.Select(attrs={"class": "form-select"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "debit": forms.NumberInput(attrs={"class": "form-control text-end", "step": "0.01", "min": "0"}),
            "credit": forms.NumberInput(attrs={"class": "form-control text-end", "step": "0.01", "min": "0"}),
        }

    def clean(self):
        cleaned = super().clean()
        debit = cleaned.get("debit") or 0
        credit = cleaned.get("credit") or 0
        if debit and credit:
            raise forms.ValidationError("Enter either Debit or Credit, not both.")
        if (debit or 0) <= 0 and (credit or 0) <= 0:
            raise forms.ValidationError("Enter a Debit or Credit amount.")
        return cleaned


JournalVoucherLineFormSet = inlineformset_factory(
    JournalVoucher,
    JournalVoucherLine,
    form=JournalVoucherLineForm,
    extra=2,
    can_delete=True,
)


class ReturnNoteForm(forms.ModelForm):
    class Meta:
        model = ReturnNote
        fields = ["invoice", "date", "narration"]
        widgets = {
            "invoice": forms.Select(attrs={"class": "form-select", "data-ui-select2": "1"}),
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "narration": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Narration"}),
        }


class ReturnNoteItemForm(forms.ModelForm):
    class Meta:
        model = ReturnNoteItem
        fields = ["product", "quantity", "rate"]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select", "data-ui-select2": "1"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control text-end", "step": "0.01", "min": "0"}),
            "rate": forms.NumberInput(attrs={"class": "form-control text-end", "step": "0.01", "min": "0"}),
        }

    def clean_quantity(self):
        q = self.cleaned_data.get("quantity")
        if q is None:
            return q
        if q <= 0:
            raise forms.ValidationError("Quantity must be greater than 0.")
        return q


ReturnNoteItemFormSet = inlineformset_factory(
    ReturnNote,
    ReturnNoteItem,
    form=ReturnNoteItemForm,
    extra=1,
    can_delete=True,
)
