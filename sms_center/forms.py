from django import forms


class AutoSMSToggleForm(forms.Form):
    auto_sms_send = forms.BooleanField(required=False, label="Auto SMS Send")

