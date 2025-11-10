# backend/core/views.py
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.timezone import now
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
    View,
)

from .forms import (
    DocumentForm,
    IncidentForm,
    IncidentManageForm,
    PaymentForm,
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
    Meeting,
    Minutes,
    Payment,
    Reservation,
    Resident,
    Resource,
)

# ------------------------------------------------
# Menú dinámico (nav_items)
# ------------------------------------------------


def has_any_perm(user, perms):
    """True si el usuario tiene al menos uno de los permisos dados."""
    return any(user.has_perm(p) for p in perms)


def build_nav_items(request):
    """Construye la lista de ítems del menú según el usuario/permiso."""
    items = []
    u = request.user
    if not u.is_authenticated:
        return items

    # Comunes a toda persona autenticada
    items.append({"label": "Avisos", "url": reverse("core:announcement_list")})
    items.append({"label": "Reuniones", "url": reverse("core:meeting_list")})
    items.append({"label": "Mis pagos", "url": reverse("core:my_payments")})
    items.append({"label": "Documentos", "url": reverse("core:documents-list")})
    items.append({"label": "Incidencias", "url": reverse("core:incident_mine")})
    items.append({"label": "Reservas", "url": reverse("core:reservation_mine")})

    # Gestión (superuser / Admin / Secretario / Presidente)
    if is_management_user(u):
        items.append({"label": "Panel", "url": reverse("core:dashboard")})

        if has_any_perm(u, ["core.view_fee", "core.add_fee", "core.change_fee"]):
            items.append({"label": "Cuotas", "url": reverse("core:fee_list")})

        if u.has_perm("core.view_payment"):
            items.append(
                {"label": "Pagos (admin)", "url": reverse("core:payment_list_admin")}
            )

        # Acceso directo a subir documento (la vista valida permisos con mixin)
        items.append(
            {"label": "Subir documento", "url": reverse("core:documents-create")}
        )

    # Presidencia (ver vecinos). No implica change_resident.
    if (u.is_superuser or u.groups.filter(name="Presidente").exists()) and u.has_perm(
        "core.view_resident"
    ):
        items.append(
            {"label": "Presidencia", "url": reverse("core:president_residents")}
        )

    # Incidencias
    if u.has_perm("core.view_incident"):
        items.append(
            {"label": "Incidencias (admin)", "url": reverse("core:incident_admin")}
        )

    # Reserva
    if u.has_perm("core.view_reservation"):
        items.append(
            {"label": "Reservas (admin)", "url": reverse("core:reservation_admin")}
        )

    return items


class NavItemsMixin:
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_items"] = build_nav_items(self.request)
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
    return render(request, "home.html", {"nav_items": build_nav_items(request)})


@login_required
@permission_required("core.view_payment", raise_exception=True)
def dashboard(request):
    return render(request, "dashboard.html", {"nav_items": build_nav_items(request)})


# ----------------------------
# Anuncios (Announcements)
# ----------------------------
class AnnouncementListView(NavItemsMixin, LoginRequiredMixin, ListView):
    model = Announcement
    template_name = "core/announcement_list.html"
    context_object_name = "avisos"

    def get_queryset(self):
        qs = super().get_queryset()
        today = now().date()
        return qs.filter(Q(visible_hasta__isnull=True) | Q(visible_hasta__gte=today))


class AnnouncementDetailView(NavItemsMixin, LoginRequiredMixin, DetailView):
    model = Announcement
    template_name = "core/announcement_detail.html"
    context_object_name = "aviso"


class AnnouncementCreateView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    permission_required = "core.add_announcement"
    model = Announcement
    fields = ["titulo", "cuerpo", "visible_hasta"]
    template_name = "core/announcement_form.html"
    success_url = reverse_lazy("core:announcement_list")

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        return super().form_valid(form)


class AnnouncementUpdateView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    permission_required = "core.change_announcement"
    model = Announcement
    fields = ["titulo", "cuerpo", "visible_hasta"]
    template_name = "core/announcement_form.html"
    success_url = reverse_lazy("core:announcement_list")


class AnnouncementDeleteView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView
):
    permission_required = "core.delete_announcement"
    model = Announcement
    template_name = "core/announcement_confirm_delete.html"
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
    template_name = "core/payment_list_admin.html"
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
    template_name = "core/payment_list_mine.html"
    context_object_name = "payments"

    def get_queryset(self):
        return (
            Payment.objects.filter(resident=self.request.user)
            .select_related("fee")
            .order_by("-created_at")
        )


class PaymentCreateForResidentView(NavItemsMixin, LoginRequiredMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = "core/payment_form.html"
    success_url = reverse_lazy("core:my_payments")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        form.instance.resident = self.request.user
        form.instance.amount = form.cleaned_data["fee"].amount
        u = self.request.user
        is_admin = (
            u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
        )
        if not is_admin:
            form.instance.status = Payment.STATUS_PENDING
        return super().form_valid(form)


class PaymentUpdateAdminView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    permission_required = "core.change_payment"
    model = Payment
    form_class = PaymentForm
    template_name = "core/payment_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_success_url(self):
        return reverse_lazy("core:payment_list_admin")


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
class DocumentListView(NavItemsMixin, ListView):
    """
    Listado de documentos con búsqueda y filtro por categoría.
    Acceso público: si no está autenticado, solo ve PUBLICO.
    """

    model = Document
    template_name = "core/documents/list.html"
    context_object_name = "docs"
    paginate_by = 12

    def get_queryset(self):
        qs = Document.objects.filter(
            is_active=True,
            visibilidad__in=allowed_visibility_for(self.request.user),
        )
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(titulo__icontains=q) | Q(descripcion__icontains=q))
        cat = self.request.GET.get("cat")
        if cat:
            qs = qs.filter(categoria_id=cat)
        return qs.select_related("categoria", "subido_por").order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categorias"] = DocumentCategory.objects.order_by("nombre")
        ctx["q"] = self.request.GET.get("q", "") or ""
        ctx["cat_selected"] = self.request.GET.get("cat", "") or ""
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


class IncidentListMineView(NavItemsMixin, LoginRequiredMixin, ListView):
    model = Incident
    template_name = "core/incidents/list_mine.html"
    context_object_name = "incidencias"
    paginate_by = 10

    def get_queryset(self):
        q = Incident.objects.filter(reportado_por=self.request.user)
        estado = self.request.GET.get("estado")
        if estado in dict(Incident.Status.choices):
            q = q.filter(status=estado)
        return q.select_related("categoria").order_by("-created_at")


class IncidentCreateView(NavItemsMixin, LoginRequiredMixin, CreateView):
    model = Incident
    form_class = IncidentForm
    template_name = "core/incidents/form.html"
    success_url = reverse_lazy("core:incident_mine")

    def form_valid(self, form):
        form.instance.reportado_por = self.request.user
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


class MyReservationsListView(NavItemsMixin, LoginRequiredMixin, ListView):
    model = Reservation
    template_name = "core/reservations/list_mine.html"
    context_object_name = "reservas"
    paginate_by = 10

    def get_queryset(self):
        qs = Reservation.objects.filter(requested_by=self.request.user)
        estado = self.request.GET.get("estado")
        recurso = self.request.GET.get("recurso")
        if estado in dict(Reservation.Status.choices):
            qs = qs.filter(status=estado)
        if recurso:
            qs = qs.filter(resource_id=recurso)
        return qs.select_related("resource").order_by("-start_at")

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

    def form_valid(self, form):
        form.instance.requested_by = self.request.user
        form.instance.status = Reservation.Status.PENDING
        messages.success(self.request, "Solicitud de reserva creada.")
        return super().form_valid(form)


class ReservationCancelView(NavItemsMixin, LoginRequiredMixin, View):
    def post(self, request, pk):
        r = get_object_or_404(Reservation, pk=pk, requested_by=request.user)
        if r.status in (Reservation.Status.PENDING, Reservation.Status.APPROVED):
            r.status = Reservation.Status.CANCELLED
            r.cancelled_at = now()
            r.save(update_fields=["status", "cancelled_at", "updated_at"])
            messages.success(request, "Reserva cancelada.")
        else:
            messages.error(request, "No es posible cancelar esta reserva.")
        return redirect("core:reservation_mine")


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
            "resource",
            "requested_by",
            "approved_by",
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
