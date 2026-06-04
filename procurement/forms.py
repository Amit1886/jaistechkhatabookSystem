from __future__ import annotations

from django import forms

from commerce.models import Product
from khataapp.models import Party
from procurement.models import SupplierProduct


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Party
        fields = ["name", "mobile", "email", "address", "whatsapp_number", "is_active"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg fw-bold",
                    "placeholder": "Supplier name",
                    "autofocus": "autofocus",
                }
            ),
            "mobile": forms.TextInput(
                attrs={"class": "form-control form-control-lg fw-bold", "placeholder": "Phone", "inputmode": "numeric"}
            ),
            "email": forms.EmailInput(attrs={"class": "form-control form-control-lg fw-bold", "placeholder": "Email"}),
            "address": forms.Textarea(attrs={"class": "form-control fw-bold", "rows": 3, "placeholder": "Address"}),
            "whatsapp_number": forms.TextInput(
                attrs={"class": "form-control fw-bold", "placeholder": "WhatsApp number", "inputmode": "numeric"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def save(self, commit=True):
        obj: Party = super().save(commit=False)
        obj.party_type = "supplier"
        if commit:
            obj.save()
        return obj


class SupplierProductForm(forms.ModelForm):
    class Meta:
        model = SupplierProduct
        fields = ["supplier", "product", "price", "moq", "delivery_days", "is_active"]
        widgets = {
            "supplier": forms.Select(attrs={"class": "form-select fw-bold"}),
            "product": forms.Select(attrs={"class": "form-select fw-bold"}),
            "price": forms.NumberInput(attrs={"class": "form-control fw-bold", "step": "0.01", "min": "0"}),
            "moq": forms.NumberInput(attrs={"class": "form-control fw-bold", "min": "1"}),
            "delivery_days": forms.NumberInput(attrs={"class": "form-control fw-bold", "min": "0"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        owner = kwargs.pop("owner", None)
        super().__init__(*args, **kwargs)
        if owner is not None:
            self.fields["supplier"].queryset = Party.objects.filter(owner=owner, party_type="supplier").order_by("name", "id")
            self.fields["product"].queryset = Product.objects.filter(owner=owner).order_by("name", "id")


class SupplierPriceUploadForm(forms.Form):
    file = forms.FileField(
        required=True,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
        help_text="Upload CSV or Excel (.xlsx). Columns: supplier, product_sku, product_name, price, moq, delivery_days",
    )

