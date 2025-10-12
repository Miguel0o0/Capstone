from django.contrib import admin
from .models import Resident, Household, Announcement, Meeting, Minutes

@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):
    list_display = ("nombre", "email", "telefono", "activo")
    search_fields = ("nombre", "email")
    list_filter = ("activo",)

@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ("direccion", "numero", "referencia")
    search_fields = ("direccion",)
    
@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("titulo", "creado_por", "visible_hasta", "creado_en")
    search_fields = ("titulo", "cuerpo")
    list_filter = ("visible_hasta", "creado_en")
    
@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("fecha", "lugar", "tema", "creado_en")
    search_fields = ("tema", "lugar")
    list_filter = ("fecha",)

@admin.register(Minutes)
class MinutesAdmin(admin.ModelAdmin):
    list_display = ("meeting", "creado_en")
    search_fields = ("meeting__tema",)
