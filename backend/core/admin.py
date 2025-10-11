from django.contrib import admin
from .models import Resident, Household

@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):
    list_display = ("nombre", "email", "telefono", "activo")
    search_fields = ("nombre", "email")
    list_filter = ("activo",)

@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ("direccion", "numero", "referencia")
    search_fields = ("direccion",)