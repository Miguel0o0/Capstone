# backend/core/urls.py
from django.urls import path

from . import views
from .views import (
    DashboardView,
    IncidentDeleteView,
    IncidentUpdateView,
    InscriptionCreateView,
    InscriptionEvidenceListAdminView,
    InscriptionEvidenceManageView,
    PaymentReceiptUploadView,
    PaymentReviewView,
    PresidentResidentsListView,
    PresidentResidentManageView,
)

app_name = "core"

urlpatterns = [
    # -----------------------------
    # Página principal y panel
    # -----------------------------
    path("", views.home, name="home"),
    path("panel/", DashboardView.as_view(), name="dashboard"),
    # -----------------------------
    # Avisos
    # -----------------------------
    path("avisos/", views.AnnouncementListView.as_view(), name="announcement_list"),
    path(
        "avisos/nuevo/",
        views.AnnouncementCreateView.as_view(),
        name="announcement_create",
    ),
    path(
        "avisos/<int:pk>/",
        views.AnnouncementDetailView.as_view(),
        name="announcement_detail",
    ),
    path(
        "avisos/<int:pk>/editar/",
        views.AnnouncementUpdateView.as_view(),
        name="announcement_edit",
    ),
    path(
    "avisos/<int:pk>/editar/",
    views.AnnouncementUpdateView.as_view(),
    name="announcement_update",
    ),  
    path(
        "avisos/<int:pk>/borrar/",
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
    # Cuotas (Fees)
    # -----------------------------
    path("fees/", views.FeeListView.as_view(), name="fee_list"),
    path("fees/nueva/", views.FeeCreateView.as_view(), name="fee_create"),
    path("fees/<int:pk>/editar/", views.FeeUpdateView.as_view(), name="fee_update"),
    # -----------------------------
    # Pagos (Payments)
    # -----------------------------
    path(
        "pagos/admin/",
        views.PaymentListAdminView.as_view(),
        name="payment_list_admin",
    ),
    path(
        "pagos/admin/nuevo/",
        views.PaymentCreateAdminView.as_view(),
        name="payment_create_admin",
    ),
    path(
        "mis-pagos/",
        views.MyPaymentsView.as_view(),
        name="my_payments",
    ),
    path(
        "pagos/nuevo/",
        views.MyPaymentsForStaffView.as_view(),
        name="payment_create",
    ),
    path(
        "pagos/<int:pk>/editar/",
        views.PaymentReviewAdminView.as_view(),
        name="payment_update_admin",
    ),
    path(
        "pagos/<int:pk>/eliminar/",
        views.PaymentDeleteAdminView.as_view(),
        name="payment_delete_admin",
    ),
        path(
        "pagos/<int:pk>/comprobante/",
        views.PaymentReceiptUploadView.as_view(),
        name="payment_receipt_upload",
    ),
        # Vecino sube comprobante
    path(
        "pagos/<int:pk>/subir-comprobante/",
        PaymentReceiptUploadView.as_view(),
        name="payment_upload_receipt",
    ),
    # Vista embebible para ver comprobante
    path(
        "pagos/admin/<int:pk>/comprobante/ver/",
        views.payment_receipt_preview,
        name="payment_receipt_preview",
    ),
    # -----------------------------
    # 👑 Presidente: Gestión de vecinos
    # -----------------------------
    path(
        "presidencia/vecinos/",
        PresidentResidentsListView.as_view(),
        name="president_residents",
    ),
    path(
        "presidencia/vecinos/<int:pk>/gestionar/",
        PresidentResidentManageView.as_view(),
        name="resident_manage",
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
    path(
        "documentos/editar/<int:pk>/",
        views.DocumentUpdateView.as_view(),
        name="documents-edit",
    ),
    path(
        "documentos/borrar/<int:pk>/",
        views.DocumentDeleteView.as_view(),
        name="documents-delete",
    ),
    path(
        "documentos/certificado-residencia/",
        views.CertificateResidenceView.as_view(),
        name="cert_residence",
    ),
    path(
        "documentos/certificado-residencia/preview/",
        views.CertificateResidencePreviewView.as_view(),
        name="cert_residence_preview",
    ),
    path(
        "documentos/certificado-residencia/pdf/",
        views.CertificateResidencePdfView.as_view(),
        name="cert_residence_pdf",
    ),
    path(
        "documentos/certificado-residencia/descargar/",
        views.CertificateResidenceDownloadView.as_view(),
        name="cert_residence_download",
    ),
    path(
        "documentos/certificado-residencia/enviar-correo/",
        views.CertificateResidenceSendEmailView.as_view(),
        name="cert_residence_send_email",
    ),
    # Salvoconducto
    path(
        "documentos/salvoconducto/",
        views.SalvoconductoView.as_view(),
        name="cert_salvoconducto",
    ),
    path(
        "documentos/salvoconducto/preview/",
        views.SalvoconductoPreviewView.as_view(),
        name="cert_salvoconducto_preview",
    ),
    path(
        "documentos/salvoconducto/pdf/",
        views.SalvoconductoPdfView.as_view(),
        name="cert_salvoconducto_pdf",
    ),
    path(
        "documentos/salvoconducto/descargar/",
        views.SalvoconductoDownloadView.as_view(),
        name="cert_salvoconducto_download",
    ),
    path(
        "documentos/salvoconducto/enviar/",
        views.SalvoconductoSendEmailView.as_view(),
        name="cert_salvoconducto_send_email",
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
    path(
        "incidencias/<int:pk>/editar/",
        IncidentUpdateView.as_view(),
        name="incident_update",
    ),
    path(
        "incidencias/<int:pk>/eliminar/",
        IncidentDeleteView.as_view(),
        name="incident_delete",
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
    # Inscripcion
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
    # Vecino sube comprobante
    path(
        "pagos/<int:pk>/subir-comprobante/",
        PaymentReceiptUploadView.as_view(),
        name="payment_upload_receipt",
    ),
    # Tesorero / Presidente revisa pago
    path(
        "pagos/admin/<int:pk>/revisar/",
        PaymentReviewView.as_view(),
        name="payment_review",
    ),
    # Notificaciónes
    path(
        "notificaciones/marcar-leidas/",
        views.NotificationsMarkReadView.as_view(),
        name="notifications_mark_read",
    ),


]

