from __future__ import annotations

from django import forms


class WhatsAppCommandForm(forms.Form):
    command = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. sale 5 ice cream 250"}),
    )


class WhatsAppSettingsForm(forms.Form):
    enabled = forms.BooleanField(required=False)
    provider = forms.ChoiceField(
        choices=[
            ("ultramsg", "UltraMsg (easy demo)"),
            ("meta_cloud_api", "Meta WhatsApp Cloud API (official)"),
            ("twilio", "Twilio WhatsApp"),
            ("gupshup", "Gupshup (BSP)"),
            ("360dialog", "360dialog (BSP)"),
            ("wati", "WATI (BSP/platform)"),
            ("interakt", "Interakt (BSP/platform)"),
            ("aisensy", "AiSensy (BSP/platform)"),
            ("infobip", "Infobip (BSP)"),
            ("vonage", "Vonage (BSP)"),
            ("messagebird", "MessageBird/Bird (BSP)"),
            ("kaleyra", "Kaleyra (BSP)"),
            ("custom_http", "Custom HTTP (any provider)"),
        ],
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    ultramsg_instance_id = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    ultramsg_token = forms.CharField(required=False, widget=forms.PasswordInput(render_value=True, attrs={"class": "form-control"}))
    webhook_secret = forms.CharField(required=False, widget=forms.PasswordInput(render_value=True, attrs={"class": "form-control"}))
