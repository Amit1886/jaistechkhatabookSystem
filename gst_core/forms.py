from django import forms
from .models import GSTRegistration, GSTCategory, GSTTransaction, FiscalYear, FiscalPeriod, GSTR1, GSTR3B


class GSTRegistrationForm(forms.ModelForm):
    class Meta:
        model = GSTRegistration
        fields = "__all__"


class GSTCategoryForm(forms.ModelForm):
    class Meta:
        model = GSTCategory
        fields = "__all__"


class GSTTransactionForm(forms.ModelForm):
    class Meta:
        model = GSTTransaction
        fields = "__all__"


class FiscalYearForm(forms.ModelForm):
    class Meta:
        model = FiscalYear
        fields = "__all__"


class FiscalPeriodForm(forms.ModelForm):
    class Meta:
        model = FiscalPeriod
        fields = "__all__"


class GSTR1Form(forms.ModelForm):
    class Meta:
        model = GSTR1
        fields = "__all__"


class GSTR3BForm(forms.ModelForm):
    class Meta:
        model = GSTR3B
        fields = "__all__"
