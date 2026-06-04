from __future__ import annotations

from django import forms


class InvoiceImageUploadForm(forms.Form):
    image = forms.ImageField(
        required=True,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
    )

