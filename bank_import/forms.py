from __future__ import annotations

from django import forms


class BankStatementUploadForm(forms.Form):
    file = forms.FileField(
        required=True,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".csv,.xlsx"}),
    )

