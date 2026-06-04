from django import forms

from reports.models import Checklist, ChecklistItem, QueryTicket


class ChecklistForm(forms.ModelForm):
    class Meta:
        model = Checklist
        fields = ["title", "notes", "due_date", "status"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Checklist title"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Notes (optional)"}),
            "due_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }


class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ["text"]
        widgets = {
            "text": forms.TextInput(attrs={"class": "form-control", "placeholder": "Add an item…"}),
        }


class QueryTicketForm(forms.ModelForm):
    class Meta:
        model = QueryTicket
        fields = ["subject", "description", "priority", "status"]
        widgets = {
            "subject": forms.TextInput(attrs={"class": "form-control", "placeholder": "Subject"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Describe your query…"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

