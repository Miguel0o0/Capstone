from django.contrib import admin

from .models import (
    Announcement,
    Document,
    DocumentCategory,
    Fee,
    Household,
    Incident,
    IncidentCategory,
    InscriptionEvidence,
    Meeting,
    Minutes,
    Payment,
    Reservation,
    Resident,
    Resource,
    ResourceCategory,
)


# ---------------------
# Residentes y Hogares
# ---------------------
@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):
    list_display = ("nombre", "email", "telefono", "activo")
    search_fields = ("nombre", "email")
    list_filter = ("activo",)


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ("direccion", "numero", "referencia")
    search_fields = ("direccion",)


# -----------
# Anuncios
# -----------
@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("titulo", "creado_por", "visible_hasta", "creado_en")
    search_fields = ("titulo", "cuerpo")
    list_filter = ("visible_hasta", "creado_en")


# -----------
# Reuniones
# -----------
@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("fecha", "lugar", "tema", "creado_en")
    search_fields = ("tema", "lugar")
    list_filter = ("fecha",)


@admin.register(Minutes)
class MinutesAdmin(admin.ModelAdmin):
    list_display = ("meeting", "creado_en")
    search_fields = ("meeting__tema",)


# -------
# Cuotas
# -------
@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    list_display = ("period", "amount")
    search_fields = ("period",)
    ordering = ("-period",)


# --------
# Pagos
# --------
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "resident",
        "origin",
        "fee",
        "reservation",
        "amount",
        "status",
        "paid_at",
        "created_at",
    )
    list_filter = (
        "status",
        "origin",
        ("fee", admin.RelatedOnlyFieldListFilter),
        ("reservation", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        "resident__username",
        "resident__first_name",
        "resident__last_name",
        "fee__period",
        "reservation__resource__nombre",
        "reservation__title",
    )
    autocomplete_fields = ("resident", "fee", "reservation")
    readonly_fields = ("created_at",)


# ---------------
# Documentos
# ---------------
@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion")
    search_fields = ("nombre",)


@admin.action(description="Marcar como INACTIVOS (soft delete)")
def marcar_inactivos(modeladmin, request, queryset):
    queryset.update(is_active=False)


@admin.action(description="Marcar como ACTIVOS")
def marcar_activos(modeladmin, request, queryset):
    queryset.update(is_active=True)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "categoria",
        "visibilidad",
        "is_active",
        "subido_por",
        "created_at",
    )
    list_filter = (
        "visibilidad",
        "is_active",
        "categoria",
        "created_at",
    )
    search_fields = ("titulo", "descripcion", "subido_por__username")
    autocomplete_fields = ("categoria", "subido_por")
    date_hierarchy = "created_at"
    actions = [marcar_inactivos, marcar_activos]
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Información",
            {
                "fields": (
                    "titulo",
                    "descripcion",
                    "categoria",
                    "visibilidad",
                    "is_active",
                )
            },
        ),
        ("Archivo", {"fields": ("archivo",)}),
        ("Metadatos", {"fields": ("subido_por", "created_at", "updated_at")}),
    )


@admin.register(IncidentCategory)
class IncidentCategoryAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("titulo", "reportado_por", "categoria", "status", "created_at")
    list_filter = ("status", "categoria", "created_at")
    search_fields = ("titulo", "descripcion", "reportado_por__username")
    autocomplete_fields = ("reportado_por", "asignada_a", "categoria")


@admin.register(ResourceCategory)
class ResourceCategoryAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "precio_por_hora", "activo")
    list_filter = ("activo", "categoria")
    search_fields = ("nombre",)
    autocomplete_fields = ("categoria",)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("resource", "title", "requested_by", "status", "start_at", "end_at")
    list_filter = ("status", "resource", "start_at")
    search_fields = ("title", "requested_by__username")
    autocomplete_fields = ("resource", "requested_by", "approved_by")


@admin.register(InscriptionEvidence)
class InscriptionEvidenceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "submitted_by",
        "resident",
        "created_at",
        "validated_by",
        "validated_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("id", "submitted_by__username", "resident__nombre")
    readonly_fields = ("created_at", "updated_at", "validated_by", "validated_at")
