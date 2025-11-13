# backend/core/views.py
import os
from io import BytesIO

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.core.mail import EmailMessage
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.utils.timezone import now
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
    View,
)

from .context_processors import nav_items as build_nav_from_cp
from .forms import IncidentResidentForm  # (vecino)
from .forms import PaymentForm  # (admin)
from .forms import ResidentPaymentStartForm  # (vecino paso 1)
from .forms import (
    AdminPaymentForm,
    AnnouncementForm,
    DocumentForm,
    IncidentManageForm,
    InscriptionCreateForm,
    InscriptionManageForm,
    ReservationForm,
    ReservationManageForm,
)
from .models import (
    Announcement,
    Document,
    DocumentCategory,
    Fee,
    Incident,
    IncidentCategory,
    InscriptionEvidence,
    Meeting,
    Minutes,
    Payment,
    Reservation,
    Resident,
    Resource,
)

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


# ------------------------------------------------
# Menú dinámico (nav_items)
# ------------------------------------------------
def has_any_perm(user, perms):
    """True si el usuario tiene al menos uno de los permisos dados."""
    return any(user.has_perm(p) for p in perms)


def build_nav_items(request):
    items = []
    u = request.user
    is_admin_or_secret = (
        u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
    )
    is_president = u.groups.filter(name="Presidente").exists()
    is_delegate = u.groups.filter(name="Delegado").exists()
    is_management = is_admin_or_secret or is_president  # mesa + presidente

    # --- Comunes a cualquier autenticado ---
    items.append({"label": "Avisos", "url": reverse("core:announcement_list")})
    items.append({"label": "Reuniones", "url": reverse("core:meeting_list")})
    items.append({"label": "Mis pagos", "url": reverse("core:payment_list_mine")})
    items.append({"label": "Incidencias", "url": reverse("core:incident_mine")})
    items.append({"label": "Reservas", "url": reverse("core:reservation_mine")})
    items.append({"label": "Documentos", "url": reverse("core:documents-list")})

    # --- Gestión (no para Delegado ni Vecino) ---
    if is_management and not is_delegate:
        items.append({"label": "Panel", "url": reverse("core:dashboard")})

        if (
            u.has_perm("core.view_fee")
            or u.has_perm("core.add_fee")
            or u.has_perm("core.change_fee")
        ):
            items.append({"label": "Cuotas (admin)", "url": reverse("core:fee_list")})

        if u.has_perm("core.view_payment"):
            items.append(
                {"label": "Pagos (admin)", "url": reverse("core:payment_list_admin")}
            )

        # << ESTA ES LA LÍNEA QUE OCULTA A VECINO: solo management con permiso >>
        if u.has_perm("core.view_reservation"):
            items.append(
                {
                    "label": "Reservas (admin)",
                    "url": reverse("core:reservation_list_admin"),
                }
            )

        # Subir documento (si corresponde)
        if u.has_perm("core.add_document") or u.has_perm("core.change_document"):
            items.append(
                {"label": "Subir documento", "url": reverse("core:documents-create")}
            )

    # Puedes mantener aquí cualquier otro menú condicional (Presidencia, etc.)
    return items


class NavItemsMixin:
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_nav_from_cp(self.request))  # {"nav_items": [...]}
        return ctx


# ------------------------------------------------
# Helpers / Mixins de permisos y roles
# ------------------------------------------------
def is_admin_or_secretary(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.groups.filter(name__in=["Admin", "Secretario"]).exists()
    )


class IsAdminOrSecretaryMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        u = self.request.user
        if not u.is_authenticated:
            return False
        return (
            u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
        )


# NUEVO: incluye Presidente como usuario de gestión
def is_management_user(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.groups.filter(name__in=["Admin", "Secretario", "Presidente"]).exists()
    )


class IsManagementMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return is_management_user(self.request.user)


class AnyPermRequiredMixin(PermissionRequiredMixin):
    def has_permission(self):
        perms = self.get_permission_required()
        if isinstance(perms, str):
            perms = (perms,)
        u = self.request.user
        return u.is_authenticated and any(u.has_perm(p) for p in perms)


def allowed_visibility_for(user):
    """Visibilidades permitidas según el usuario."""
    if user and (
        user.is_superuser
        or user.is_staff
        or user.groups.filter(name__in=["Admin", "Secretario"]).exists()
    ):
        return [
            Document.Visibility.PUBLICO,
            Document.Visibility.RESIDENTES,
            Document.Visibility.STAFF,
        ]
    if user and user.is_authenticated:
        return [Document.Visibility.PUBLICO, Document.Visibility.RESIDENTES]
    return [Document.Visibility.PUBLICO]


# ----------------------------
# Vistas base
# ----------------------------
def home(request):
    return render(request, "home.html")


@login_required
@permission_required("core.view_payment", raise_exception=True)
def dashboard(request):
    return render(request, "dashboard.html")


# ----------------------------
# Anuncios (Announcements)
# ----------------------------
class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ["titulo", "cuerpo", "visible_hasta"]
        widgets = {
            # selector nativo de fecha
            "visible_hasta": forms.DateInput(attrs={"type": "date"}),
        }


class IsAnnouncementManagerMixin(UserPassesTestMixin):
    """Permite a Admin/Secretario/Delegado (o quien tenga add/change) crear/editar avisos."""

    raise_exception = True  # 403 en vez de redirigir

    def test_func(self):
        u = self.request.user
        if not u.is_authenticated:
            return False
        # Usa permisos, que ya reflejan tus grupos (Admin/Secretario/Delegado)
        return u.has_perm("core.add_announcement") or u.has_perm(
            "core.change_announcement"
        )


class AnnouncementListView(LoginRequiredMixin, ListView):
    model = Announcement
    template_name = "core/announcement/announcement_list.html"  # ver sección 3
    context_object_name = "avisos"


class AnnouncementDetailView(LoginRequiredMixin, DetailView):
    model = Announcement
    template_name = "core/announcement/announcement_detail.html"
    context_object_name = "aviso"


class AnnouncementCreateView(
    LoginRequiredMixin, IsAnnouncementManagerMixin, CreateView
):
    model = Announcement
    form_class = AnnouncementForm
    template_name = "core/announcement/announcement_form.html"
    success_url = reverse_lazy("core:announcement_list")

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        return super().form_valid(form)


class AnnouncementUpdateView(
    LoginRequiredMixin, IsAnnouncementManagerMixin, UpdateView
):
    model = Announcement
    form_class = AnnouncementForm
    template_name = "core/announcement/announcement_form.html"
    success_url = reverse_lazy("core:announcement_list")


class AnnouncementDeleteView(
    LoginRequiredMixin, IsAnnouncementManagerMixin, DeleteView
):
    model = Announcement
    template_name = "core/announcement/announcement_confirm_delete.html"
    success_url = reverse_lazy("core:announcement_list")


# ----------------------------
# Reuniones (Meetings)
# ----------------------------
class MeetingListView(NavItemsMixin, LoginRequiredMixin, ListView):
    model = Meeting
    template_name = "core/meeting_list.html"
    context_object_name = "reuniones"


class MeetingDetailView(NavItemsMixin, LoginRequiredMixin, DetailView):
    model = Meeting
    template_name = "core/meeting_detail.html"
    context_object_name = "reunion"


class MeetingCreateView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    permission_required = "core.add_meeting"
    model = Meeting
    fields = ["fecha", "lugar", "tema"]
    template_name = "core/meeting_form.html"
    success_url = reverse_lazy("core:meeting_list")


class MeetingUpdateView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    permission_required = "core.change_meeting"
    model = Meeting
    fields = ["fecha", "lugar", "tema"]
    template_name = "core/meeting_form.html"
    success_url = reverse_lazy("core:meeting_list")


class MeetingDeleteView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView
):
    permission_required = "core.delete_meeting"
    model = Meeting
    template_name = "core/meeting_confirm_delete.html"
    success_url = reverse_lazy("core:meeting_list")


# ----------------------------
# Actas (Minutes)
# ----------------------------
class MinutesDetailView(NavItemsMixin, LoginRequiredMixin, DetailView):
    model = Minutes
    template_name = "core/minutes_detail.html"
    context_object_name = "acta"


class MinutesCreateView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    permission_required = "core.add_minutes"
    model = Minutes
    fields = ["meeting", "texto", "archivo"]
    template_name = "core/minutes_form.html"
    success_url = reverse_lazy("core:meeting_list")


class MinutesUpdateView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    permission_required = "core.change_minutes"
    model = Minutes
    fields = ["meeting", "texto", "archivo"]
    template_name = "core/minutes_form.html"
    success_url = reverse_lazy("core:meeting_list")


class MinutesDeleteView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView
):
    permission_required = "core.delete_minutes"
    model = Minutes
    template_name = "core/minutes_confirm_delete.html"
    success_url = reverse_lazy("core:meeting_list")


# ----------------------------
# Cuotas (Fees)
# ----------------------------
class FeeListView(NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "core.view_fee"
    model = Fee
    template_name = "core/fee_list.html"
    context_object_name = "fees"


class FeeCreateView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    permission_required = "core.add_fee"
    model = Fee
    fields = ("period", "amount")
    template_name = "core/fee_form.html"
    success_url = reverse_lazy("core:fee_list")


class FeeUpdateView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    permission_required = "core.change_fee"
    model = Fee
    fields = ("period", "amount")
    template_name = "core/fee_form.html"
    success_url = reverse_lazy("core:fee_list")


# ----------------------------
# Pagos (Payments)
# ----------------------------
class PaymentListAdminView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, ListView
):
    permission_required = "core.view_payment"
    model = Payment
    template_name = "core/payment/payment_list_admin.html"
    context_object_name = "payments"

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("resident", "fee")
            .order_by("-created_at")
        )
        period = self.request.GET.get("period")
        if period:
            qs = qs.filter(fee__period=period)
        return qs


class MyPaymentsView(NavItemsMixin, LoginRequiredMixin, ListView):
    model = Payment
    template_name = "core/payment/payment_list_mine.html"
    context_object_name = "payments"

    def get_queryset(self):
        return (
            Payment.objects.filter(resident=self.request.user)
            .select_related("fee")
            .order_by("-created_at")
        )


class PaymentCreateForResidentView(NavItemsMixin, LoginRequiredMixin, CreateView):
    """
    Paso 1 (vecino): seleccionar deuda pendiente.
    """

    model = Payment
    form_class = ResidentPaymentStartForm
    template_name = (
        "core//payment/payment_start_form.html"  # plantilla simple de selección
    )
    success_url = reverse_lazy("core:my_payments")  # por ahora volvemos a la lista

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        # Creamos el registro de pago en estado PENDIENTE (sin método de pago aún)
        form.instance.resident = self.request.user
        form.instance.amount = form.cleaned_data["fee"].amount
        form.instance.status = Payment.STATUS_PENDING
        messages.success(
            self.request,
            "Pago iniciado. En el siguiente paso podrás elegir el medio de pago (pendiente).",
        )
        return super().form_valid(form)


class PaymentCreateAdminView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    """
    Vista para que Tesorero/Presidente/Admin creen pagos manualmente.
    """

    permission_required = "core.add_payment"
    model = Payment
    form_class = AdminPaymentForm
    template_name = "core/payment/payment_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Para que el template sepa que está en modo administración
        context["is_admin_payment"] = True
        return context

    def get_success_url(self):
        return reverse_lazy("core:payment_list_admin")


# --- Pagos: edición Tesorería/Admin ---
class PaymentUpdateAdminView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    permission_required = "core.change_payment"
    model = Payment
    form_class = PaymentForm
    template_name = "core/payment/payment_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_admin_payment"] = True
        return context

    def get_success_url(self):
        return reverse_lazy("core:payment_list_admin")


# --- Pagos: borrado Tesorería/Admin ---
class PaymentDeleteAdminView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Payment
    template_name = "core/payment/payment_confirm_delete.html"
    permission_required = "core.delete_payment"
    success_url = reverse_lazy("core:payment_list_admin")


# ------------------------------------------------
# 👑 Presidencia — Gestión de vecinos
# ------------------------------------------------
class PresidentResidentsListView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, ListView
):
    permission_required = "core.view_resident"
    model = Resident
    template_name = "core/president_residents.html"
    context_object_name = "vecinos"
    paginate_by = 10
    raise_exception = True

    def get_queryset(self):
        qs = super().get_queryset().select_related("user").order_by("nombre")
        q = self.request.GET.get("q")
        activo = self.request.GET.get("activo")
        if q:
            qs = qs.filter(Q(nombre__icontains=q) | Q(email__icontains=q))
        if activo in ("si", "no"):
            qs = qs.filter(activo=(activo == "si"))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "") or ""
        ctx["activo"] = self.request.GET.get("activo", "") or ""
        return ctx

    def has_permission(self):
        u = self.request.user
        if not u.is_authenticated:
            return False
        if u.is_superuser:
            return True
        is_president = u.groups.filter(name="Presidente").exists()
        return is_president and super().has_permission()


class PresidentResidentToggleActiveView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, View
):
    permission_required = "core.change_resident"
    raise_exception = True

    def handle_no_permission(self):
        messages.error(
            self.request, "No tienes permiso para cambiar el estado de vecinos."
        )
        return super().handle_no_permission()

    def post(self, request, pk):
        vecino = Resident.objects.filter(pk=pk).first()
        if vecino is None:
            messages.error(request, "El vecino solicitado no existe.")
            return redirect("core:president_residents")

        try:
            vecino.activo = not vecino.activo
            vecino.save(update_fields=["activo"])
            messages.success(
                request,
                f"Vecino «{vecino.nombre}» "
                f"{'activado' if vecino.activo else 'desactivado'} correctamente.",
            )
        except Exception:
            messages.error(
                request, "No se pudo actualizar el estado. Intenta nuevamente."
            )
        return redirect("core:president_residents")


# ------------------------------------------------
# Documentos (listar, crear, descargar)
# ------------------------------------------------
class DocumentListView(NavItemsMixin, LoginRequiredMixin, ListView):
    model = Document
    template_name = "core/documents/list.html"
    context_object_name = "docs"
    paginate_by = 20

    def get_queryset(self):
        qs = Document.objects.filter(is_active=True).order_by("-created_at")

        u = self.request.user

        # Si no está autenticado: sólo documentos públicos
        if not u.is_authenticated:
            return qs.filter(visibilidad=Document.Visibility.PUBLICO)

        # Vecinos y cualquier usuario NO staff:
        if not (u.is_staff or u.has_perm("core.view_all_documents")):
            qs = qs.filter(
                visibilidad__in=[
                    Document.Visibility.PUBLICO,
                    Document.Visibility.RESIDENTES,
                ]
            )
        # Staff (admin/secretario/presidente con permisos) ve todo.

        # Filtro de búsqueda
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(titulo__icontains=q) | Q(descripcion__icontains=q))

        # Filtro por categoría
        cat = self.request.GET.get("cat")
        if cat:
            qs = qs.filter(categoria_id=cat)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        ctx["cat_selected"] = self.request.GET.get("cat") or ""
        ctx["categorias"] = DocumentCategory.objects.all().order_by("nombre")
        return ctx


class DocumentCreateView(
    NavItemsMixin, LoginRequiredMixin, IsManagementMixin, CreateView
):
    """Subir/crear documentos (Superuser/Admin/Secretario/Presidente)."""

    model = Document
    form_class = DocumentForm
    template_name = "core/documents/form.html"
    success_url = reverse_lazy("core:documents-list")

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.subido_por = self.request.user
        obj.save()
        return super().form_valid(form)


def document_download_view(request, pk: int):
    """
    Descarga segura con chequeo de visibilidad.
    Responde 404 si el usuario no tiene permiso para 'ver' el documento.
    """
    doc = get_object_or_404(Document, pk=pk, is_active=True)
    if doc.visibilidad not in allowed_visibility_for(request.user):
        raise Http404()
    if not doc.archivo:
        raise Http404()

    path = doc.archivo.path
    if not os.path.exists(path):
        raise Http404()

    return FileResponse(open(path, "rb"), as_attachment=True, filename=doc.filename)


class IsDocsManagerMixin(UserPassesTestMixin):
    """Usuarios que pueden gestionar documentos (crear/editar)."""

    raise_exception = True

    def test_func(self):
        u = self.request.user
        return u.is_authenticated and (
            u.has_perm("core.add_document") or u.has_perm("core.change_document")
        )


class DocumentUpdateView(
    NavItemsMixin, LoginRequiredMixin, IsDocsManagerMixin, UpdateView
):
    model = Document
    form_class = DocumentForm
    template_name = "core/documents/form.html"
    success_url = reverse_lazy("core:documents-list")


class DocumentDeleteView(
    NavItemsMixin, LoginRequiredMixin, UserPassesTestMixin, DeleteView
):
    model = Document
    template_name = "core/documents/confirm_delete.html"
    success_url = reverse_lazy("core:documents-list")
    raise_exception = True

    def test_func(self):
        u = self.request.user
        return u.is_authenticated and u.has_perm("core.delete_document")


# ---------------------------
# Certificado de residencia
# ---------------------------
class CertificateResidenceForm(forms.Form):
    nombre = forms.CharField(label="Nombre completo", max_length=120)
    rut = forms.CharField(label="RUT", max_length=20)
    direccion = forms.CharField(label="Dirección", max_length=180)
    comuna = forms.CharField(label="Comuna", max_length=80)
    motivo = forms.CharField(label="Motivo", max_length=120, required=False)
    enviar_email = forms.BooleanField(label="Enviar a mi correo", required=False)


class CertificateResidenceView(NavItemsMixin, LoginRequiredMixin, View):
    template_name = "core/documents/cert_residence_form.html"

    def get(self, request):
        form = CertificateResidenceForm(
            initial={
                "nombre": getattr(request.user, "first_name", "")
                + " "
                + getattr(request.user, "last_name", ""),
            }
        )
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = CertificateResidenceForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        data = form.cleaned_data

        # 1) Generar PDF simple (ReportLab) o fallback HTML
        filename = f"certificado_residencia_{slugify(data['nombre'])}.pdf"
        pdf_bytes = None

        if REPORTLAB_AVAILABLE:
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            text = c.beginText(60, 790)
            text.setFont("Helvetica", 12)
            lines = [
                "CERTIFICADO DE RESIDENCIA",
                "",
                f"Nombre        : {data['nombre']}",
                f"RUT           : {data['rut']}",
                f"Dirección     : {data['direccion']}, {data['comuna']}",
                f"Motivo        : {data.get('motivo') or 'No especificado'}",
                "",
                "La Junta de Vecinos certifica que los datos anteriores corresponden a",
                "un vecino inscrito y con domicilio dentro de la jurisdicción.",
                "",
                f"Emitido el {now().strftime('%d/%m/%Y %H:%M')}.",
            ]
            for ln in lines:
                text.textLine(ln)
            c.drawText(text)
            c.showPage()
            c.save()
            pdf_bytes = buffer.getvalue()
            buffer.close()

        # 2) Enviar por email si lo pidió
        if data.get("enviar_email") and getattr(request.user, "email", None):
            try:
                email = EmailMessage(
                    subject="Certificado de residencia",
                    body="Adjuntamos su certificado de residencia.",
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    to=[request.user.email],
                )
                if pdf_bytes:
                    email.attach(filename, pdf_bytes, "application/pdf")
                else:
                    # Fallback con HTML si no hay reportlab
                    html_body = render_to_string(
                        "core/documents/cert_residence_email.html", {"data": data}
                    )
                    email.content_subtype = "html"
                    email.body = html_body
                email.send(fail_silently=True)
                messages.success(request, "Enviamos el certificado a tu correo.")
            except Exception:
                messages.warning(
                    request,
                    "No se pudo enviar el email. Descárgalo desde el navegador.",
                )

        # 3) Descargar en el navegador
        if pdf_bytes:
            return FileResponse(
                BytesIO(pdf_bytes), as_attachment=True, filename=filename
            )
        else:
            # Fallback: mostrar HTML (el usuario puede imprimir a PDF)
            html = render_to_string(
                "core/documents/cert_residence_fallback.html", {"data": data}
            )
            return render(
                request, "core/documents/cert_residence_fallback.html", {"data": data}
            )


# ------------------------------------------------
# Incidencias
# ------------------------------------------------
class IncidentListMineView(NavItemsMixin, LoginRequiredMixin, ListView):
    """
    Página de 'Mis incidencias'.

    - Vecino: ve SOLO las incidencias que él reportó.
    - Delegado / Admin / Secretario / Presidente / Tesorero / superuser:
      ven TODAS las incidencias de la comunidad.
    """

    model = Incident
    template_name = "core/incidents/list_mine.html"
    context_object_name = "incidencias"
    paginate_by = 10

    def get_queryset(self):
        qs = Incident.objects.all().select_related("categoria", "reportado_por")
        estado = self.request.GET.get("estado")
        if estado in dict(Incident.Status.choices):
            qs = qs.filter(status=estado)
        return qs.order_by("-created_at")


class IncidentCreateView(NavItemsMixin, LoginRequiredMixin, CreateView):
    """
    Vecino: formulario simplificado.
    """

    model = Incident
    form_class = IncidentResidentForm
    template_name = "core/incidents/form_resident.html"
    success_url = reverse_lazy("core:incident_mine")

    def form_valid(self, form):
        form.instance.reportado_por = self.request.user
        messages.success(self.request, "Incidencia reportada. ¡Gracias por avisar!")
        return super().form_valid(form)


class IncidentListAdminView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, ListView
):
    permission_required = "core.view_incident"
    model = Incident
    template_name = "core/incidents/list_admin.html"
    context_object_name = "incidencias"
    paginate_by = 15

    def get_queryset(self):
        qs = Incident.objects.all().select_related(
            "categoria", "reportado_por", "asignada_a"
        )
        estado = self.request.GET.get("estado")
        if estado in dict(Incident.Status.choices):
            qs = qs.filter(status=estado)
        cat = self.request.GET.get("cat")
        if cat:
            qs = qs.filter(categoria_id=cat)
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categorias"] = IncidentCategory.objects.order_by("nombre")
        ctx["estado"] = self.request.GET.get("estado", "")
        ctx["cat_selected"] = self.request.GET.get("cat", "")
        return ctx


class IncidentListPublicView(NavItemsMixin, LoginRequiredMixin, ListView):
    model = Incident
    template_name = "core/incidents/list_public.html"
    context_object_name = "incidencias"
    paginate_by = 15

    def get_queryset(self):
        # Por ahora, todas ordenadas por fecha (luego puedes filtrar por comuna/barrio)
        return Incident.objects.select_related("categoria", "reportado_por").order_by(
            "-created_at"
        )


class IncidentUpdateView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    """
    Editar incidencia desde la vista de 'Mis incidencias'.

    - Delegado / mesa / superuser: pueden editar cualquier incidencia.
    - Vecino: solo puede editar incidencias que él mismo reportó.
    """

    permission_required = "core.change_incident"
    model = Incident
    form_class = IncidentResidentForm  # usamos el mismo formulario sencillo del vecino
    template_name = "core/incidents/form_resident.html"
    success_url = reverse_lazy("core:incident_mine")

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user

        # Roles de gestión: pueden editar cualquier incidencia
        if (
            u.is_superuser
            or u.groups.filter(
                name__in=["Admin", "Secretario", "Presidente", "Tesorero", "Delegado"]
            ).exists()
        ):
            return qs

        # Vecino: solo puede editar incidencias reportadas por él
        return qs.filter(reportado_por=u)

    def form_valid(self, form):
        messages.success(self.request, "Incidencia actualizada correctamente.")
        return super().form_valid(form)


class IncidentDeleteView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView
):
    """
    Eliminar incidencia desde 'Mis incidencias'.

    - Delegado / mesa / superuser: pueden borrar cualquier incidencia.
    - Vecino: solo puede borrar incidencias que él mismo reportó.
    """

    permission_required = "core.delete_incident"
    model = Incident
    template_name = "core/incidents/incident_confirm_delete.html"
    success_url = reverse_lazy("core:incident_mine")

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user

        # Roles de gestión: pueden borrar cualquier incidencia
        if (
            u.is_superuser
            or u.groups.filter(
                name__in=["Admin", "Secretario", "Presidente", "Tesorero", "Delegado"]
            ).exists()
        ):
            return qs

        # Vecino: solo puede borrar incidencias reportadas por él
        return qs.filter(reportado_por=u)


class IncidentManageView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    permission_required = "core.change_incident"
    model = Incident
    form_class = IncidentManageForm
    template_name = "core/incidents/manage_form.html"

    def form_valid(self, form):
        obj = form.save(commit=False)
        if obj.status in (Incident.Status.RESOLVED, Incident.Status.REJECTED):
            obj.closed_at = obj.closed_at or now()
        else:
            obj.closed_at = None
        obj.save()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("core:incident_admin")


# ------------------------------------------------
# Reservas
# ------------------------------------------------
class MyReservationsListView(NavItemsMixin, LoginRequiredMixin, ListView):
    model = Reservation
    template_name = "core/reservations/list_mine.html"
    context_object_name = "reservas"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user

        # Base: traemos recurso y usuario para evitar queries extra
        qs = Reservation.objects.select_related("resource", "requested_by")

        # Usuarios de gestión (ven TODAS las reservas)
        grupos_gestion = ["Delegado", "Tesorero", "Secretario", "Presidente"]
        es_gestion = (
            user.is_superuser or user.groups.filter(name__in=grupos_gestion).exists()
        )

        if es_gestion:
            return qs.order_by("-start_at")

        # Vecino (u otro rol no gestión): solo ve sus reservas
        return qs.filter(requested_by=user).order_by("-start_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recursos"] = Resource.objects.filter(activo=True).order_by("nombre")
        ctx["estado"] = self.request.GET.get("estado", "")
        ctx["recurso_selected"] = self.request.GET.get("recurso", "")
        return ctx


class ReservationCreateView(NavItemsMixin, LoginRequiredMixin, CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = "core/reservations/form.html"
    success_url = reverse_lazy("core:reservation_mine")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request  # para leer ?tipo=... en el form
        return kwargs

    def form_valid(self, form):
        form.instance.requested_by = self.request.user
        form.instance.status = Reservation.Status.PENDING
        messages.success(self.request, "Solicitud de reserva creada.")
        return super().form_valid(form)


class ReservationCancelView(LoginRequiredMixin, View):
    def post(self, request, pk):
        reserva = get_object_or_404(Reservation, pk=pk)

        # 👇 Solo quien creó la reserva puede cancelarla
        if reserva.requested_by != request.user:
            return HttpResponseForbidden(
                "No puedes cancelar reservas de otros usuarios."
            )

        if reserva.status in [
            Reservation.Status.PENDING,
            Reservation.Status.APPROVED,
        ]:
            reserva.status = Reservation.Status.CANCELLED
            reserva.cancelled_at = timezone.now()
            reserva.save()

        messages.success(request, "Reserva cancelada.")
        return redirect("core:reservation_list_mine")


class ReservationListAdminView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, ListView
):
    permission_required = "core.view_reservation"
    model = Reservation
    template_name = "core/reservations/list_admin.html"
    context_object_name = "reservas"
    paginate_by = 15

    def get_queryset(self):
        qs = Reservation.objects.all().select_related(
            "resource", "requested_by", "approved_by"
        )
        estado = self.request.GET.get("estado")
        recurso = self.request.GET.get("recurso")
        if estado in dict(Reservation.Status.choices):
            qs = qs.filter(status=estado)
        if recurso:
            qs = qs.filter(resource_id=recurso)
        return qs.order_by("-start_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recursos"] = Resource.objects.order_by("nombre")
        ctx["estado"] = self.request.GET.get("estado", "")
        ctx["recurso_selected"] = self.request.GET.get("recurso", "")
        return ctx


class ReservationManageView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    permission_required = "core.change_reservation"
    model = Reservation
    form_class = ReservationManageForm
    template_name = "core/reservations/manage_form.html"

    def form_valid(self, form):
        obj = form.save(commit=False)
        if obj.status == Reservation.Status.APPROVED:
            obj.approved_by = obj.approved_by or self.request.user
            obj.approved_at = obj.approved_at or now()
            obj.cancelled_at = None
        elif obj.status in (Reservation.Status.REJECTED, Reservation.Status.CANCELLED):
            obj.cancelled_at = obj.cancelled_at or now()
        obj.save()
        messages.success(self.request, "Reserva actualizada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("core:reservation_admin")


# ------------------------------------------------
# Inscripciones (validación de domicilio)
# ------------------------------------------------
class InscriptionCreateView(CreateView):
    model = InscriptionEvidence
    form_class = InscriptionCreateForm
    template_name = "core/inscription/form.html"
    success_url = reverse_lazy("core:home")

    def form_valid(self, form):
        if self.request.user.is_authenticated:
            form.instance.submitted_by = self.request.user
        messages.success(
            self.request,
            "Tu solicitud fue enviada. La Junta revisará tu documento para validar tu domicilio.",
        )
        return super().form_valid(form)


class InscriptionEvidenceListAdminView(PermissionRequiredMixin, ListView):
    permission_required = "core.view_inscriptionevidence"
    model = InscriptionEvidence
    template_name = "core/inscription/list_admin.html"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().order_by("-created_at")
        status = self.request.GET.get("status")
        return qs.filter(status=status) if status else qs


class InscriptionEvidenceManageView(PermissionRequiredMixin, UpdateView):
    permission_required = "core.change_inscriptionevidence"
    model = InscriptionEvidence
    form_class = InscriptionManageForm
    template_name = "core/inscription/manage_form.html"

    def form_valid(self, form):
        obj = form.save(commit=False)
        if form.cleaned_data["status"] == obj.Status.APPROVED:
            obj.approve(self.request.user, form.cleaned_data.get("note", ""))
        elif form.cleaned_data["status"] == obj.Status.REJECTED:
            obj.reject(self.request.user, form.cleaned_data.get("note", ""))
        obj.save()
        messages.success(self.request, "Inscripción actualizada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("core:insc_admin")
