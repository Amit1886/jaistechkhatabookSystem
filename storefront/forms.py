from __future__ import annotations

from django import forms

from .models import VendorProductListing


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=200)
    email = forms.EmailField()
    mobile = forms.CharField(max_length=15, required=False)

    line1 = forms.CharField(max_length=255, label="Address")
    line2 = forms.CharField(max_length=255, required=False)
    landmark = forms.CharField(max_length=255, required=False)
    pincode = forms.CharField(max_length=10)
    district = forms.CharField(max_length=80, required=False)
    state = forms.CharField(max_length=80, required=False)
    alternate_mobile = forms.CharField(max_length=15, required=False)
    latitude = forms.DecimalField(required=False, max_digits=9, decimal_places=6)
    longitude = forms.DecimalField(required=False, max_digits=9, decimal_places=6)

    coupon_code = forms.CharField(max_length=50, required=False)
    referrer_code = forms.CharField(max_length=24, required=False)


class VendorLoginHintForm(forms.Form):
    # Placeholder (uses existing accounts login); kept for future.
    pass


class VendorProductListingForm(forms.ModelForm):
    class Meta:
        model = VendorProductListing
        fields = ["is_online", "title", "description", "price_override", "is_featured"]
        widgets = {
            "is_online": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "price_override": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
