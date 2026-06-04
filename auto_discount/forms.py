from __future__ import annotations

from decimal import Decimal
from typing import Any

from django import forms
from django.forms import BaseFormSet, formset_factory


class AutoDiscountSettingsForm(forms.Form):
    enable_auto_discount = forms.BooleanField(required=False)
    min_profit_percentage = forms.DecimalField(min_value=Decimal("0"), decimal_places=2, max_digits=6, initial=Decimal("10.00"))


class SlabRowForm(forms.Form):
    min_qty = forms.IntegerField(min_value=1, required=False)
    discount = forms.DecimalField(min_value=Decimal("0"), max_value=Decimal("100"), decimal_places=2, max_digits=6, required=False)


class _BaseSlabFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        # basic dedupe validation (min_qty should not repeat)
        seen: set[int] = set()
        for f in self.forms:
            if not hasattr(f, "cleaned_data"):
                continue
            min_qty = f.cleaned_data.get("min_qty")
            discount = f.cleaned_data.get("discount")
            if min_qty in (None, "") and discount in (None, ""):
                continue
            if min_qty is None or discount is None:
                raise forms.ValidationError("Har row me Min Qty aur Discount dono bharna zaroori hai.")
            if int(min_qty) in seen:
                raise forms.ValidationError("Min Qty duplicate nahi ho sakta. Har slab ka Min Qty unique rakho.")
            seen.add(int(min_qty))


SlabFormSet = formset_factory(SlabRowForm, formset=_BaseSlabFormSet, extra=0, can_delete=True)


def slabs_from_formset(formset: SlabFormSet) -> list[dict[str, Any]]:
    slabs: list[dict[str, Any]] = []
    for f in formset.forms:
        cd = getattr(f, "cleaned_data", {}) or {}
        if cd.get("DELETE"):
            continue
        min_qty = cd.get("min_qty")
        discount = cd.get("discount")
        if min_qty is None and discount is None:
            continue
        if min_qty is None or discount is None:
            continue
        slabs.append({"min_qty": int(min_qty), "discount": float(discount)})
    slabs.sort(key=lambda x: x["min_qty"])
    return slabs
