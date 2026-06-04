# full path: khataapp/forms.py

from django import forms
from django.contrib.auth import get_user_model

from .models import Party, Transaction, SupplierPayment, FieldAgent, ContactMessage
from commerce.models import Order


# ----------------- Party Form -----------------
class PartyForm(forms.ModelForm):
    class Meta:
        model = Party
        fields = ['name', 'mobile', 'email', 'party_type']
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg fw-bold",
                    "placeholder": "Party name",
                    "data-kb-primary": "1",
                    "autofocus": "autofocus",
                }
            ),
            "mobile": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg fw-bold",
                    "placeholder": "Mobile number",
                    "inputmode": "numeric",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control form-control-lg fw-bold",
                    "placeholder": "Email (optional)",
                }
            ),
            "party_type": forms.Select(
                attrs={
                    "class": "form-select form-select-lg fw-bold",
                }
            ),
        }


# ----------------- Transaction Form -----------------
class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['party', 'txn_type', 'amount', 'notes']


# ----------------- User Profile (Dashboard) -----------------
class UserProfileDashboardForm(forms.ModelForm):

    class Meta:
        model = None   # set in __init__
        exclude = ["user"]

    def __init__(self, *args, **kwargs):
        from accounts.models import UserProfile   # ✅ lazy import (safe)
        self._meta.model = UserProfile
        super().__init__(*args, **kwargs)

        if self.instance and getattr(self.instance, "user", None):
            if "email" in self.fields:
                self.fields["email"].disabled = True
            if "mobile" in self.fields:
                self.fields["mobile"].disabled = True


# ----------------- User Profile Plan Change Form -----------------
def get_plan_model():
    """Lazy import of Plan model to avoid circular import"""
    from plans.models import Plan
    return Plan


class UserProfilePlanForm(forms.ModelForm):

    class Meta:
        model = None   # set in __init__
        fields = ['plan']

    def __init__(self, *args, **kwargs):
        from accounts.models import UserProfile   # ✅ lazy import
        self._meta.model = UserProfile
        super().__init__(*args, **kwargs)

        Plan = get_plan_model()
        self.fields['plan'].queryset = Plan.objects.all()


# ----------------- Contact Form -----------------
class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'mobile', 'message']


# ----------------- Supplier Payment Form -----------------
class SupplierPaymentForm(forms.ModelForm):
    class Meta:
        model = SupplierPayment
        fields = ['order', 'amount', 'payment_mode', 'reference', 'notes', 'payment_date']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields['order'].queryset = Order.objects.filter(
                owner=user,
                order_type='PURCHASE',
                due_amount__gt=0
            ).select_related('party')

        self.fields["order"].widget.attrs.update(
            {
                "class": "form-select form-select-lg fw-bold",
                "data-kb-primary": "1",
                "autofocus": "autofocus",
            }
        )
        self.fields["amount"].widget.attrs.update({"class": "form-control form-control-lg fw-bold"})
        self.fields["payment_mode"].widget.attrs.update({"class": "form-select form-select-lg fw-bold"})
        self.fields["reference"].widget.attrs.update({"class": "form-control form-control-lg fw-bold"})
        self.fields["payment_date"].widget.attrs.update({"class": "form-control form-control-lg fw-bold"})
        self.fields["notes"].widget.attrs.update({"class": "form-control fw-bold"})

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Payment amount must be greater than zero.")
        return amount

    def clean(self):
        cleaned = super().clean()
        order = cleaned.get("order")
        amount = cleaned.get("amount")
        if order and amount and amount > (order.due_amount or 0):
            raise forms.ValidationError("Payment amount cannot be greater than the outstanding amount.")
        return cleaned


# ----------------- Field Agent Form -----------------
class FieldAgentForm(forms.ModelForm):
    class Meta:
        model = FieldAgent
        fields = ["user", "role", "mobile", "assigned_parties", "is_active", "notes"]
        widgets = {
            "assigned_parties": forms.SelectMultiple(attrs={"size": 8}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        owner = kwargs.pop("owner", None)
        super().__init__(*args, **kwargs)

        User = get_user_model()
        qs = User.objects.filter(is_active=True).exclude(is_superuser=True)

        if owner:
            qs = qs.exclude(id=owner.id)
            self.fields["assigned_parties"].queryset = Party.objects.filter(owner=owner).order_by("name")

        if not (self.instance and self.instance.pk):
            qs = qs.filter(field_agent_profile__isnull=True)

        if self.instance and self.instance.pk:
            qs = qs | User.objects.filter(id=self.instance.user_id)

        self.fields["user"].queryset = qs.distinct()

        for name, field in self.fields.items():
            base = "agent-input"
            if name == "is_active":
                field.widget.attrs.update({"class": "agent-check"})
            elif name == "assigned_parties":
                field.widget.attrs.update({"class": f"{base} agent-multi", "size": 10})
            else:
                current = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = f"{current} {base}".strip()
