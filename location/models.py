from django.db import models


class Country(models.Model):
    company = models.ForeignKey(
        "core_settings.CompanySettings",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="countries",
        help_text="Optional tenant scope. Keep null for global master data.",
    )
    name = models.CharField(max_length=120)
    iso2 = models.CharField(max_length=2, blank=True, db_index=True)
    iso3 = models.CharField(max_length=3, blank=True)
    phone_code = models.CharField(max_length=8, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["company", "name"]),
            models.Index(fields=["company", "iso2"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="uniq_country_company_name"),
        ]

    def __str__(self) -> str:
        return self.name


class State(models.Model):
    company = models.ForeignKey(
        "core_settings.CompanySettings",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="states",
        help_text="Optional tenant scope. Keep null for global master data.",
    )
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="states")
    name = models.CharField(max_length=140)
    code = models.CharField(max_length=16, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["company", "country", "name"])]
        constraints = [
            models.UniqueConstraint(fields=["company", "country", "name"], name="uniq_state_company_country_name"),
        ]

    def __str__(self) -> str:
        return f"{self.name}"


class District(models.Model):
    company = models.ForeignKey(
        "core_settings.CompanySettings",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="districts",
        help_text="Optional tenant scope. Keep null for global master data.",
    )
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name="districts")
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["company", "state", "name"])]
        constraints = [
            models.UniqueConstraint(fields=["company", "state", "name"], name="uniq_district_company_state_name"),
        ]

    def __str__(self) -> str:
        return f"{self.name}"


class Pincode(models.Model):
    company = models.ForeignKey(
        "core_settings.CompanySettings",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="pincodes",
        help_text="Optional tenant scope. Keep null for global master data.",
    )
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="pincodes")
    code = models.CharField(max_length=12, db_index=True)
    locality = models.CharField(max_length=160, blank=True)
    city = models.CharField(max_length=160, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]
        indexes = [
            models.Index(fields=["company", "code"]),
            models.Index(fields=["district", "code"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uniq_pincode_company_code"),
        ]

    def __str__(self) -> str:
        return self.code

