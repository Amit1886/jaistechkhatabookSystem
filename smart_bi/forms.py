from __future__ import annotations

from django import forms

from commerce.models import Product
from smart_bi.models import DuplicateInvoiceSettings, FestivalCampaign


class FestivalCampaignForm(forms.ModelForm):
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-control", "data-select2": "1"}),
        help_text="Leave empty to apply discount on all products.",
    )

    class Meta:
        model = FestivalCampaign
        fields = [
            "name",
            "start_date",
            "end_date",
            "discount_type",
            "discount_value",
            "theme",
            "status",
            "banner_image",
            "products",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "discount_type": forms.Select(attrs={"class": "form-control"}),
            "discount_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "theme": forms.TextInput(attrs={"class": "form-control", "placeholder": "diwali / holi / new_year"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        if owner is not None:
            self.fields["products"].queryset = Product.objects.filter(owner=owner).order_by("name")

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date must be on/after start date.")
        return cleaned


class DuplicateInvoiceSettingsForm(forms.ModelForm):
    class Meta:
        model = DuplicateInvoiceSettings
        fields = ["enabled", "window_minutes", "strict_mode", "similarity_threshold"]
        widgets = {
            "enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "window_minutes": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "strict_mode": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "similarity_threshold": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0", "max": "100"}),
        }
