# backend/core/urls.py
from django.urls import path

from . import views
from .views import (
    InscriptionCreateView,
    InscriptionEvidenceListAdminView,
    InscriptionEvidenceManageView,
)

app_name = "core"

urlpatterns = [
    # -----------------------------
    # Página principal y panel
    # -----------------------------
    path("", views.home, name="home"),
    path("panel/", views.dashboard, name="dashboard"),
    # -----------------------------
    # Avisos
    # -----------------------------
    path("avisos/", views.AnnouncementListView.as_view(), name="announcement_list"),
    path(
        "avisos/<int:pk>/",
        views.AnnouncementDetailView.as_view(),
        name="announcement_detail",
    ),
    path(
        "avisos/nuevo/",
        views.AnnouncementCreateView.as_view(),
        name="announcement_create",
    ),
    path(
        "avisos/<int:pk>/editar/",
        views.AnnouncementUpdateView.as_view(),
        name="announcement_update",
    ),
    path(
        "avisos/<int:pk>/eliminar/",
        views.AnnouncementDeleteView.as_view(),
        name="announcement_delete",
    ),
    # -----------------------------
    # Reuniones
    # -----------------------------
    path("reuniones/", views.MeetingListView.as_view(), name="meeting_list"),
    path(
        "reuniones/<int:pk>/",
        views.MeetingDetailView.as_view(),
        name="meeting_detail",
    ),
    path("reuniones/nueva/", views.MeetingCreateView.as_view(), name="meeting_create"),
    path(
        "reuniones/<int:pk>/editar/",
        views.MeetingUpdateView.as_view(),
        name="meeting_update",
    ),
    path(
        "reuniones/<int:pk>/eliminar/",
        views.MeetingDeleteView.as_view(),
        name="meeting_delete",
    ),
    # -----------------------------
    # Actas
    # -----------------------------
    path("actas/<int:pk>/", views.MinutesDetailView.as_view(), name="minutes_detail"),
    path("actas/nueva/", views.MinutesCreateView.as_view(), name="minutes_create"),
    path(
        "actas/<int:pk>/editar/",
        views.MinutesUpdateView.as_view(),
        name="minutes_update",
    ),
    path(
        "actas/<int:pk>/eliminar/",
        views.MinutesDeleteView.as_view(),
        name="minutes_delete",
    ),
    # -----------------------------
    # Cuotas (Fees)
    # -----------------------------
    path("fees/", views.FeeListView.as_view(), name="fee_list"),
    path("fees/nueva/", views.FeeCreateView.as_view(), name="fee_create"),
    path("fees/<int:pk>/editar/", views.FeeUpdateView.as_view(), name="fee_update"),
    # -----------------------------
    # Pagos (Payments)
    # -----------------------------
    path(
        "pagos/admin/", views.PaymentListAdminView.as_view(), name="payment_list_admin"
    ),
    path("mis-pagos/", views.MyPaymentsView.as_view(), name="my_payments"),
    path(
        "pagos/nuevo/",
        views.PaymentCreateForResidentView.as_view(),
        name="payment_create",
    ),
    path(
        "pagos/<int:pk>/editar/",
        views.PaymentUpdateAdminView.as_view(),
        name="payment_update_admin",
    ),
    # -----------------------------
    # 👑 Presidente: Gestión de vecinos
    # -----------------------------
    path(
        "presidencia/vecinos/",
        views.PresidentResidentsListView.as_view(),
        name="president_residents",
    ),
    path(
        "presidencia/vecinos/<int:pk>/toggle/",
        views.PresidentResidentToggleActiveView.as_view(),
        name="resident_toggle",
    ),
    # -----------------------------
    # Documentos
    # -----------------------------
    path(
        "documentos/",
        views.DocumentListView.as_view(),
        name="documents-list",
    ),
    path(
        "documentos/nuevo/",
        views.DocumentCreateView.as_view(),
        name="documents-create",
    ),
    path(
        "documentos/<int:pk>/descargar/",
        views.document_download_view,
        name="documents-download",
    ),
    # Incidencias
    path("incidencias/", views.IncidentListPublicView.as_view(), name="incident_list"),
    path(
        "incidencias/nueva/", views.IncidentCreateView.as_view(), name="incident_create"
    ),
    path(
        "incidencias/mis-incidencias/",
        views.IncidentListMineView.as_view(),
        name="incident_mine",
    ),
    path(
        "incidencias/admin/",
        views.IncidentListAdminView.as_view(),
        name="incident_admin",
    ),
    path(
        "incidencias/<int:pk>/gestionar/",
        views.IncidentManageView.as_view(),
        name="incident_manage",
    ),
    # Reserva de Recursos
    # Reservas
    path(
        "reservas/mis-reservas/",
        views.MyReservationsListView.as_view(),
        name="reservation_mine",
    ),
    path(
        "reservas/nueva/",
        views.ReservationCreateView.as_view(),
        name="reservation_create",
    ),
    path(
        "reservas/<int:pk>/cancelar/",
        views.ReservationCancelView.as_view(),
        name="reservation_cancel",
    ),
    path(
        "reservas/admin/",
        views.ReservationListAdminView.as_view(),
        name="reservation_admin",
    ),
    path(
        "reservas/<int:pk>/gestionar/",
        views.ReservationManageView.as_view(),
        name="reservation_manage",
    ),
    path("inscripcion/", InscriptionCreateView.as_view(), name="insc_create"),
    path(
        "inscripcion/admin/",
        InscriptionEvidenceListAdminView.as_view(),
        name="insc_admin",
    ),
    path(
        "inscripcion/<int:pk>/gestionar/",
        InscriptionEvidenceManageView.as_view(),
        name="insc_manage",
    ),
]
