from django.contrib import admin

from .models import Country, District, Pincode, State


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "iso2", "company", "is_active")
    list_filter = ("is_active", "company")
    search_fields = ("name", "iso2", "iso3")


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "country", "company", "is_active")
    list_filter = ("is_active", "company", "country")
    search_fields = ("name", "code")


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "company", "is_active")
    list_filter = ("is_active", "company", "state")
    search_fields = ("name",)


@admin.register(Pincode)
class PincodeAdmin(admin.ModelAdmin):
    list_display = ("code", "locality", "city", "district", "company", "is_active")
    list_filter = ("is_active", "company", "district")
    search_fields = ("code", "locality", "city")

