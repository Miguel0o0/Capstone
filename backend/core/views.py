# backend/core/views.py
import os
from io import BytesIO

from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.core.mail import EmailMessage
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponseRedirect
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
    FormView,
    ListView,
    TemplateView,
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
    MeetingForm,
    ReservationForm,
    ReservationManageForm,
    ReservationCancelForm,
    PaymentReviewForm,
    PaymentReviewForm,
    PaymentReceiptUploadForm
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


def user_es_moderador_incidencias(user):
    """
    Devuelve True si el usuario puede gestionar incidencias de otros vecinos.

    En tu caso:
    - Admin
    - Secretario
    - Presidente
    - Delegado
    - superuser
    """
    return user.is_authenticated and (
        user.is_superuser
        or user.groups.filter(
            name__in=["Admin", "Secretario", "Presidente", "Delegado"]
        ).exists()
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


class DashboardView(NavItemsMixin, LoginRequiredMixin, TemplateView):
    """
    Panel del Presidente: muestra el equipo de gestión
    (Presidente, Secretario, Tesorero, Delegado).
    """

    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Roles que consideramos parte de la mesa de gestión
        roles_gestion = ["Presidente", "Secretario", "Tesorero", "Delegado"]

        # Residentes cuyo usuario pertenece a alguno de esos grupos
        equipo = (
            Resident.objects.filter(user__groups__name__in=roles_gestion)
            .select_related("user")
            .order_by("user__groups__name", "nombre")
            .distinct()
        )

        ctx["equipo_gestion"] = equipo
        ctx["roles_gestion"] = roles_gestion
        return ctx


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
    form_class = MeetingForm  # 👈 antes usaba fields = [...]
    template_name = "core/meeting_form.html"
    success_url = reverse_lazy("core:meeting_list")


class MeetingUpdateView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    permission_required = "core.change_meeting"
    model = Meeting
    form_class = MeetingForm  # 👈 igual aquí
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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user

        groups = set(u.groups.values_list("name", flat=True))

        is_secretary = "Secretario" in groups
        is_treasurer = "Tesorero" in groups
        is_president = "Presidente" in groups
        is_delegate = "Delegado" in groups

        # Título (simple para todos)
        ctx["page_title"] = "Pagos"

        # Puede crear pagos manuales (crear pago)
        ctx["can_create_admin_payment"] = u.has_perm("core.add_payment")

        # Puede iniciar su propio pago (realizar pago)
        # Delegado + Tesorero + Presidente
        ctx["can_start_own_payment"] = (
            is_delegate or is_treasurer or is_president
        )

        return ctx

class MyPaymentsView(LoginRequiredMixin, ListView):
    template_name = "core/payment/payment_list_mine.html"
    context_object_name = "payments"

    def get_queryset(self):
        return Payment.objects.filter(
            resident=self.request.user,
            status=Payment.STATUS_PENDING,
        ).order_by("-created_at")


class PaymentCreateForResidentView(NavItemsMixin, LoginRequiredMixin, FormView):
    """
    Paso 1: el usuario selecciona uno de SUS pagos pendientes.
    No se crea un Payment nuevo, solo se marca que inicia el pago.
    """

    form_class = ResidentPaymentStartForm
    template_name = "core/payment/payment_start_form.html"
    success_url = reverse_lazy("core:my_payments")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        # El Payment ya existe (lo creó la reserva o un admin).
        payment = form.cleaned_data["payment"]

        # Aquí más adelante podrás redirigir a "paso 2" (medio de pago, etc.)
        # Por ahora solo mostramos un mensaje y volvemos a "Mis pagos".
        messages.success(
            self.request,
            f"Pago seleccionado: {payment}. En el siguiente paso se implementará la elección del medio de pago.",
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
class PaymentReviewAdminView(PermissionRequiredMixin, UpdateView):
    permission_required = "core.change_payment"
    model = Payment
    form_class = PaymentReviewForm
    template_name = "core/payment/review.html"  # <-- carpeta + archivo correcto

    def get_queryset(self):
        # Si quieres ver todos los pagos:
        return Payment.objects.all()
        # (más adelante se puede filtrar por estado si quieres)

    def form_valid(self, form):
        payment = form.save(commit=False)

        # Si lo marcan como pagado:
        if payment.status == Payment.STATUS_PAID:
            # Método helper del modelo (si lo tienes)
            if hasattr(payment, "mark_as_paid"):
                payment.mark_as_paid(
                    review_comment=form.cleaned_data.get("review_comment", ""),
                    staff_user=self.request.user,
                )
            else:
                # Versión explícita por si no tienes mark_as_paid
                from django.utils import timezone

                payment.review_comment = form.cleaned_data.get("review_comment", "")
                payment.reviewed_by = self.request.user
                payment.reviewed_at = timezone.now()
                payment.paid_at = timezone.now()
                payment.save(
                    update_fields=[
                        "status",
                        "review_comment",
                        "reviewed_by",
                        "reviewed_at",
                        "paid_at",
                    ]
                )
        else:
            # Cualquier otro estado (pending, pending_review, cancelled)
            payment.review_comment = form.cleaned_data.get("review_comment", "")
            if not payment.reviewed_by:
                from django.utils import timezone

                payment.reviewed_by = self.request.user
                payment.reviewed_at = timezone.now()
            payment.save(
                update_fields=["status", "review_comment", "reviewed_by", "reviewed_at"]
            )

        messages.success(self.request, "Pago actualizado correctamente.")
        return redirect("core:payment_list_admin")



# --- Pagos: borrado Tesorería/Admin ---
class PaymentDeleteAdminView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Payment
    template_name = "core/payment/payment_confirm_delete.html"
    permission_required = "core.delete_payment"
    success_url = reverse_lazy("core:payment_list_admin")
    
class PaymentReceiptUploadView(LoginRequiredMixin, UpdateView):
    model = Payment
    form_class = PaymentReceiptUploadForm
    template_name = "core/payment/payment_receipt_form.html"

    def get_queryset(self):
        # Solo permitir subir comprobante de pagos PENDIENTES del usuario
        return Payment.objects.filter(
            resident=self.request.user,
            status=Payment.STATUS_PENDING,
        )

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.receipt_uploaded_at = timezone.now()
        obj.status = Payment.STATUS_PENDING_REVIEW  # 👈 importante
        obj.save()

        messages.success(
            self.request,
            "Comprobante subido correctamente. El tesorero revisará tu pago.",
        )
        return redirect("core:my_payments")
    
class PaymentReviewView(PermissionRequiredMixin, UpdateView):
    permission_required = "core.change_payment"
    model = Payment
    form_class = PaymentReviewForm
    # usamos el template que está en la carpeta payment
    template_name = "core/payment/review.html"

    def get_queryset(self):
        # aquí ves todos los pagos; si quieres filtrar por estado, lo haces acá
        return Payment.objects.all()

    def form_valid(self, form):
        from django.utils import timezone

        payment = form.save(commit=False)

        # registrar quién revisó y cuándo
        payment.reviewed_by = self.request.user
        payment.reviewed_at = timezone.now()

        # si lo marcan como pagado y no tenía fecha de pago, la seteamos
        if payment.status == Payment.STATUS_PAID and payment.paid_at is None:
            payment.paid_at = timezone.now()
        # si prefieres que al marcarlo como pendiente se borre la fecha de pago:
        # elif payment.status != Payment.STATUS_PAID:
        #     payment.paid_at = None

        payment.save(update_fields=[
            "status",
            "review_comment",
            "reviewed_by",
            "reviewed_at",
            "paid_at",
        ])

        messages.success(self.request, "Pago actualizado correctamente.")
        return redirect("core:payment_list_admin")
    
# Pagos – vista para que los perfiles de gestión suban su propio comprobante
class MyPaymentsForStaffView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "core.view_payment"   # el mismo permiso que uses en PaymentListAdminView
    model = Payment
    template_name = "core/payment/payment_list_mine.html"
    context_object_name = "payments"

    def get_queryset(self):
        # mismos pagos que ve el vecino: solo los del usuario logueado
        return Payment.objects.filter(resident=self.request.user).order_by("-created_at")




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
        qs = (
            super()
            .get_queryset()
            .select_related("user")
            .prefetch_related("user__groups")
            .order_by("nombre")
        )
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


class PresidentResidentManageView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, View
):
    permission_required = "core.change_resident"
    raise_exception = True
    template_name = "core/president_resident_manage.html"

    def _get_resident(self, pk):
        return Resident.objects.filter(pk=pk).select_related("user").first()

    def handle_no_permission(self):
        messages.error(
            self.request, "No tienes permiso para gestionar vecinos."
        )
        return super().handle_no_permission()

    def get(self, request, pk):
        vecino = self._get_resident(pk)
        if vecino is None:
            messages.error(request, "El vecino solicitado no existe.")
            return redirect("core:president_residents")

        # acción inicial sugerida según si está activo o no
        initial_action = "deactivate" if vecino.activo else "activate"
        form = PresidentResidentManageForm(initial={"action": initial_action})

        context = {
            "resident": vecino,
            "form": form,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        vecino = self._get_resident(pk)
        if vecino is None:
            messages.error(request, "El vecino solicitado no existe.")
            return redirect("core:president_residents")

        form = PresidentResidentManageForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Revisa los datos del formulario.")
            return render(
                request, self.template_name, {"resident": vecino, "form": form}
            )

        action = form.cleaned_data["action"]
        message = (form.cleaned_data.get("message") or "").strip()

        # Email del vecino
        email = vecino.email or getattr(getattr(vecino, "user", None), "email", None)

        # --- Aplicar acción en la BD ---
        decision_label = ""
        accion_humana = ""

        if action == "deactivate":
            vecino.activo = False
            vecino.save(update_fields=["activo"])
            if vecino.user:
                vecino.user.is_active = False
                vecino.user.save(update_fields=["is_active"])
            decision_label = "desactivada (dada de baja)"
            accion_humana = "dar de baja tu cuenta"

        elif action == "activate":
            vecino.activo = True
            vecino.save(update_fields=["activo"])
            if vecino.user:
                vecino.user.is_active = True
                vecino.user.save(update_fields=["is_active"])
            decision_label = "activada"
            accion_humana = "activar tu cuenta"

        elif action == "delete":
            # Soft delete: desactivamos la cuenta
            vecino.activo = False
            vecino.save(update_fields=["activo"])
            if vecino.user:
                vecino.user.is_active = False
                vecino.user.save(update_fields=["is_active"])
            decision_label = "eliminada"
            accion_humana = "eliminar tu cuenta"

        else:
            messages.error(request, "Acción no reconocida.")
            return redirect("core:president_residents")

        # --- Enviar correo al vecino (si tiene email) ---
        if email:
            subject = "Gestión de tu cuenta – Junta de Vecinos UT"
            cuerpo = (
                f"Hola {vecino.nombre},\n\n"
                "Te informamos que la directiva de la Junta de Vecinos UT ha realizado "
                f"la siguiente gestión sobre tu cuenta: {accion_humana}.\n\n"
            )

            if message:
                cuerpo += f"Mensaje del presidente:\n{message}\n\n"

            cuerpo += (
                "Si tienes dudas o crees que se trata de un error, por favor "
                "contacta a la directiva respondiendo este correo.\n\n"
                "Saludos,\n"
                "Junta de Vecinos UT\n"
            )

            try:
                email_msg = EmailMessage(
                    subject=subject,
                    body=cuerpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                email_msg.send(fail_silently=False)
            except Exception as e:
                print("ERROR enviando correo de gestión de vecino:", e)
                messages.warning(
                    request,
                    "La acción se aplicó, pero hubo un problema al enviar el correo al vecino.",
                )

        messages.success(
            request,
            f"Acción aplicada sobre «{vecino.nombre}»: cuenta {decision_label}.",
        )
        return redirect("core:president_residents")


# ------------------------------------------------
# 👑 Presidencia — Gestión avanzada de vecinos
# ------------------------------------------------

class PresidentResidentManageForm(forms.Form):
    ACTION_CHOICES = (
        ("deactivate", "Dar de baja"),
        ("activate", "Activar cuenta"),
        ("delete", "Eliminar cuenta"),
    )

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(
            attrs={
                "class": "resident-select",
            }
        ),
        label="Acción a realizar",
    )

    message = forms.CharField(
        label="Mensaje para el vecino (opcional)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "resident-message",
                "placeholder": "Explica brevemente el motivo de la decisión",
            }
        ),
    )


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
        # 1) Guardar el documento con el usuario que lo sube
        obj = form.save(commit=False)
        obj.subido_por = self.request.user
        obj.save()

        # 2) Crear automáticamente un aviso relacionado
        titulo_aviso = f"Nuevo documento: {obj.titulo}"

        cuerpo_aviso = (
            "Se ha publicado un nuevo documento en la Junta de Vecinos.\n\n"
            f"Título: {obj.titulo}\n"
        )
        if obj.descripcion:
            cuerpo_aviso += f"Descripción: {obj.descripcion}\n\n"
        cuerpo_aviso += "Puedes revisarlo en la sección Documentos del sitio."

        Announcement.objects.create(
            titulo=titulo_aviso,
            cuerpo=cuerpo_aviso,  # 👈 aquí está el cambio
            creado_por=self.request.user,
        )

        messages.success(
            self.request,
            "Documento subido correctamente y aviso publicado para los vecinos.",
        )

        return redirect(self.success_url)


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

COMUNA_JUNTA = "San Joaquín"  # todos los vecinos son de esta comuna

class CertificateResidenceForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo",
        max_length=120,
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Ej: Presentar en el trabajo / colegio / institución, etc.",
            }
        ),
    )


def build_certificate_residence_pdf(data):
    """
    Genera el PDF del certificado de residencia y devuelve los bytes.
    data es un dict con nombre, rut, direccion, comuna, motivo.
    """
    if not REPORTLAB_AVAILABLE:
        return None

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Título interno del PDF (lo que se ve en el visor del navegador)
    c.setTitle("Certificado de Residencia - Junta UT")

    # Encabezado
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 60, "JUNTA DE VECINOS UT")

    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 90, "CERTIFICADO DE RESIDENCIA")

    # Comenzamos el texto del cuerpo un poco más abajo
    text_obj = c.beginText()
    text_obj.setTextOrigin(70, height - 140)
    text_obj.setFont("Helvetica", 12)

    # Datos del vecino, ordenados
    text_obj.textLine("La Directiva de la Junta de Vecinos UT certifica que:")

    text_obj.moveCursor(0, 15)  # Espacio

    text_obj.textLine(f"  Nombre Completo : {data['nombre']}")
    text_obj.textLine(f"  Rut             : {data['rut']}")
    text_obj.textLine(f"  Domicilio       : {data['direccion']}")
    text_obj.textLine(f"  Comuna          : {data['comuna']}")

    text_obj.moveCursor(0, 20)

    # Párrafo de residencia
    text_obj.textLine(
        "Que, según los antecedentes registrados en esta Junta de Vecinos,"
    )
    text_obj.textLine(
        "la persona individualizada precedentemente reside de forma permanente"
    )
    text_obj.textLine(
        "en el domicilio indicado, dentro del territorio jurisdiccional de la Junta."
    )

    text_obj.moveCursor(0, 20)

    # Motivo (si existe)
    if data.get("motivo"):
        text_obj.textLine(
            f"El presente certificado se extiende a petición del interesado para:"
        )
        text_obj.textLine(f"  {data['motivo']}.")
    else:
        text_obj.textLine(
            "El presente certificado se extiende a petición del interesado,"
        )
        text_obj.textLine(
            "para los fines que estime convenientes."
        )

    text_obj.moveCursor(0, 25)

    # Fecha de emisión
    fecha_str = now().strftime("%d/%m/%Y")
    text_obj.textLine(
        f"Se firma en la comuna de {data['comuna']}, a {fecha_str}."
    )

    c.drawText(text_obj)
    
    # Firma 
    firma_path = os.path.join(
        settings.BASE_DIR,
        "static",
        "img",
        "firma_presidente.jpg",
    )


    # Dibuja la imagen de la firma si existe
    if os.path.exists(firma_path):
        # Coordenadas aproximadas (ajusta si quieres moverla)
        firma_width = 180  # ancho en puntos
        firma_height = 60  # alto en puntos
        x = (width - firma_width) / 2  # centrado horizontal
        y = 120  # altura desde la base de la página

        c.drawImage(
            firma_path,
            x,
            y,
            width=firma_width,
            height=firma_height,
            mask="auto",
            preserveAspectRatio=True,
            anchor="c",
        )

    # Texto bajo la firma
    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, 100, "Presidente Junta de Vecinos UT")

    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes




class CertificateResidenceView(NavItemsMixin, LoginRequiredMixin, View):
    """
    Paso 1: mostrar formulario (solo motivo) y guardar datos completos en sesión
    usando la información del vecino asociado al usuario.
    """
    template_name = "core/documents/cert_residence_form.html"

    def _get_resident(self, request):
        from .models import Resident  # por si no está importado arriba

        vecino = (
            Resident.objects.filter(user=request.user)
            .select_related("user")
            .first()
        )
        return vecino

    def get(self, request):
        vecino = self._get_resident(request)
        if not vecino:
            messages.warning(
                request,
                "Tu usuario aún no está asociado a un vecino. "
                "Contacta a la directiva para registrar tus datos."
            )
            return redirect("core:documents-list")

        form = CertificateResidenceForm()
        contexto = {
            "form": form,
            "resident": vecino,
            "comuna": COMUNA_JUNTA,
        }
        return render(request, self.template_name, contexto)

    def post(self, request):
        vecino = self._get_resident(request)
        if not vecino:
            messages.warning(
                request,
                "Tu usuario aún no está asociado a un vecino. "
                "Contacta a la directiva para registrar tus datos."
            )
            return redirect("core:documents-list")

        form = CertificateResidenceForm(request.POST)
        if not form.is_valid():
            contexto = {
                "form": form,
                "resident": vecino,
                "comuna": COMUNA_JUNTA,
            }
            return render(request, self.template_name, contexto)

        motivo = (form.cleaned_data.get("motivo") or "").strip()

        # Construimos los datos definitivos a partir del vecino + motivo
        nombre = vecino.nombre or request.user.get_full_name() or request.user.username
        data = {
            "nombre": nombre,
            "rut": vecino.rut or "",
            "direccion": vecino.direccion or "",
            "comuna": COMUNA_JUNTA,
            "motivo": motivo,
        }

        # Guardamos los datos en sesión para usarlos en la vista previa / PDF / email
        request.session["cert_res_data"] = data

        return redirect("core:cert_residence_preview")

class CertificateResidencePreviewView(NavItemsMixin, LoginRequiredMixin, View):
    """
    Paso 2: mostrar vista previa con iframe + botones.
    """
    template_name = "core/documents/cert_residence_preview.html"

    def get(self, request):
        data = request.session.get("cert_res_data")
        if not data:
            messages.warning(request, "Primero debes completar el formulario del certificado.")
            return redirect("core:cert_residence")

        return render(request, self.template_name, {"data": data})

@method_decorator(xframe_options_exempt, name="dispatch")
class CertificateResidencePdfView(LoginRequiredMixin, View):
    """
    Devuelve el PDF para el iframe (inline).
    """
    def get(self, request):
        data = request.session.get("cert_res_data")
        if not data:
            raise Http404("No hay datos de certificado en la sesión.")

        pdf_bytes = build_certificate_residence_pdf(data)
        if not pdf_bytes:
            # Si no hay reportlab, devolvemos el HTML fallback dentro del iframe
            return render(
                request,
                "core/documents/cert_residence_fallback.html",
                {"data": data},
            )

        return FileResponse(
            BytesIO(pdf_bytes),
            as_attachment=False,
            filename="certificado_residencia.pdf",
            content_type="application/pdf",
        )


class CertificateResidenceDownloadView(LoginRequiredMixin, View):
    """
    Botón 'Descargar PDF'.
    """
    def get(self, request):
        data = request.session.get("cert_res_data")
        if not data:
            messages.warning(request, "Primero debes generar el certificado.")
            return redirect("core:cert_residence")

        pdf_bytes = build_certificate_residence_pdf(data)
        if not pdf_bytes:
            messages.warning(
                request,
                "No se pudo generar el PDF en este momento.",
            )
            return redirect("core:cert_residence_preview")

        return FileResponse(
            BytesIO(pdf_bytes),
            as_attachment=True,
            filename="certificado_residencia.pdf",
            content_type="application/pdf",
        )


class CertificateResidenceSendEmailView(LoginRequiredMixin, View):
    def get(self, request):
        data = request.session.get("cert_res_data")
        if not data:
            messages.warning(request, "Primero debes generar el certificado.")
            return redirect("core:cert_residence")

        if not getattr(request.user, "email", None):
            messages.warning(request, "Tu usuario no tiene un correo configurado.")
            return redirect("core:cert_residence_preview")

        pdf_bytes = build_certificate_residence_pdf(data)
        if not pdf_bytes:
            messages.warning(
                request,
                "No se pudo generar el PDF para enviarlo por correo.",
            )
            return redirect("core:cert_residence_preview")

        # Nombre para el saludo
        nombre_saludo = (
            request.user.first_name
            or data.get("nombre")
            or request.user.username
        )

        # Cuerpo del correo (texto plano)
        cuerpo = (
            f"Estimado/a {nombre_saludo},\n\n"
            "Adjuntamos en este correo su Certificado de Residencia emitido por la Junta "
            "de Vecinos UT.\n\n"
            "Este documento acredita que usted reside en el siguiente domicilio:\n"
            f" - Dirección: {data.get('direccion')}\n"
            f" - Comuna   : {data.get('comuna')}\n\n"
            "Le recordamos que este certificado ha sido generado en base a los datos "
            "entregados por usted a través de la plataforma de la Junta.\n"
            "En caso de detectar algún error, por favor póngase en contacto con la "
            "directiva para solicitar la corrección correspondiente.\n\n"
            "Atentamente,\n"
            "Junta de Vecinos UT\n"
        )

        try:
            email = EmailMessage(
                subject="Certificado de residencia",
                body=cuerpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[request.user.email],
            )
            email.attach(
                "certificado_residencia.pdf",
                pdf_bytes,
                "application/pdf",
            )
            email.send(fail_silently=False)
            messages.success(request, "Enviamos el certificado a tu correo.")
        except Exception as e:
            print("ERROR enviando certificado:", e)
            messages.warning(
                request,
                "Hubo un problema al enviar el correo con el certificado.",
            )

        return redirect("core:cert_residence_preview")



# ---------------------------
# Salvoconducto de mudanza
# ---------------------------
class SalvoconductoForm(forms.Form):
    domicilio_destino = forms.CharField(
        label="Domicilio de destino",
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Ej: Calle Falsa 123, depto 4",
                "class": "input",
            }
        ),
    )
    fecha_mudanza = forms.DateField(
        label="Fecha de mudanza",
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "input",
            }
        ),
    )



def build_salvoconducto_pdf(data):
    """
    Genera el PDF del salvoconducto de mudanza y devuelve los bytes.
    data viene desde sesión, así que fecha_mudanza puede ser date o string ISO.
    """
    if not REPORTLAB_AVAILABLE:
        return None

    # Normalizar fecha de mudanza
    fecha_raw = data.get("fecha_mudanza")
    if hasattr(fecha_raw, "strftime"):
        # Es un objeto date
        fecha_mudanza = fecha_raw
    else:
        # Suponemos string "YYYY-MM-DD"
        from datetime import date
        try:
            año, mes, dia = map(int, str(fecha_raw).split("-"))
            fecha_mudanza = date(año, mes, dia)
        except Exception:
            fecha_mudanza = None

    fecha_mudanza_str = (
        fecha_mudanza.strftime("%d/%m/%Y") if fecha_mudanza else str(fecha_raw)
    )
    fecha_emision_str = now().strftime("%d/%m/%Y")

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Título del documento (visor del navegador)
    c.setTitle("Salvoconducto de Mudanza - Junta UT")

    # Encabezado
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 60, "JUNTA DE VECINOS UT")

    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 90, "SALVOCONDUCTO DE MUDANZA")

    # Cuerpo del texto
    text = c.beginText()
    text.setTextOrigin(70, height - 140)
    text.setFont("Helvetica", 12)

    # Intro
    text.textLine("La Directiva de la Junta de Vecinos UT hace constar que:")
    text.moveCursor(0, 15)

    # Datos del vecino ordenados
    text.textLine(f"  Nombre Completo   : {data['nombre']}")
    text.textLine(f"  Rut                           : {data['rut']}")
    text.textLine(f"  Comuna           : {data['comuna']}")
    text.moveCursor(0, 15)

    # Domicilios y fecha de mudanza
    text.textLine("Que la persona individualizada precedentemente ha informado su traslado")
    text.textLine("de domicilio, en los siguientes términos:")
    text.moveCursor(0, 15)
    text.textLine(f"  Domicilio Origen    : {data['domicilio_origen']}")
    text.textLine(f"  Domicilio Destino   : {data['domicilio_destino']}")
    text.textLine(f"  Fecha Mudanza       : {fecha_mudanza_str}")

    text.moveCursor(0, 20)

    # Párrafo legal
    text.textLine(
        "El presente salvoconducto se emite para los fines de control y traslado,"
    )
    text.textLine(
        "y podrá ser presentado ante la autoridad competente cuando así se requiera."
    )

    text.moveCursor(0, 25)

    # Cierre con fecha y firma
    text.textLine(
        f"Se firma en la comuna de {data['comuna']}, a {fecha_emision_str}."
    )

    # Dibujamos todo el texto del cuerpo
    c.drawText(text)

    # --- Firma (igual que en el certificado de residencia) ---
    firma_path = os.path.join(
        settings.BASE_DIR,
        "static",
        "img",
        "firma_presidente.jpg",
    )

    if os.path.exists(firma_path):
        # Coordenadas aproximadas (ajusta si quieres moverla)
        firma_width = 180  # ancho en puntos
        firma_height = 60  # alto en puntos
        x = (width - firma_width) / 2  # centrado horizontal
        y = 120  # altura desde la parte inferior

        c.drawImage(
            firma_path,
            x,
            y,
            width=firma_width,
            height=firma_height,
            mask="auto",
            preserveAspectRatio=True,
            anchor="c",
        )

    # Texto bajo la firma
    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, 100, "Presidente Junta de Vecinos UT")

    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


class SalvoconductoView(NavItemsMixin, LoginRequiredMixin, View):
    """
    Paso 1: formulario de salvoconducto.
    Muestra los datos del vecino en modo solo lectura
    y solo pide domicilio de destino + fecha de mudanza.
    """

    template_name = "core/documents/salvoconducto_form.html"

    def _get_resident(self, request):
        return (
            Resident.objects.filter(user=request.user)
            .select_related("user")
            .first()
        )

    def get(self, request):
        vecino = self._get_resident(request)
        if not vecino:
            messages.warning(
                request,
                "Tu usuario aún no está asociado a un vecino. "
                "Contacta a la directiva para registrar tus datos."
            )
            return redirect("core:documents-list")

        form = SalvoconductoForm()
        contexto = {
            "form": form,
            "resident": vecino,
            "comuna": COMUNA_JUNTA,  # ya la tienes definida arriba
        }
        return render(request, self.template_name, contexto)

    def post(self, request):
        vecino = self._get_resident(request)
        if not vecino:
            messages.warning(
                request,
                "Tu usuario aún no está asociado a un vecino. "
                "Contacta a la directiva para registrar tus datos."
            )
            return redirect("core:documents-list")

        form = SalvoconductoForm(request.POST)
        if not form.is_valid():
            contexto = {
                "form": form,
                "resident": vecino,
                "comuna": COMUNA_JUNTA,
            }
            return render(request, self.template_name, contexto)

        # Construimos los datos finales combinando ficha + formulario
        nombre = (
            vecino.nombre
            or request.user.get_full_name()
            or request.user.username
        )

        data = {
            "nombre": nombre,
            "rut": vecino.rut or "",
            "domicilio_origen": vecino.direccion or "",
            "domicilio_destino": form.cleaned_data["domicilio_destino"],
            "comuna": COMUNA_JUNTA,
            # Guardamos como string ISO para la sesión
            "fecha_mudanza": form.cleaned_data["fecha_mudanza"].isoformat(),
        }

        request.session["salvoconducto_data"] = data
        return redirect("core:cert_salvoconducto_preview")




class SalvoconductoPreviewView(NavItemsMixin, LoginRequiredMixin, View):
    """
    Paso 2: vista previa con iframe + botones.
    """
    template_name = "core/documents/salvoconducto_preview.html"

    def get(self, request):
        data = request.session.get("salvoconducto_data")
        if not data:
            messages.warning(request, "Primero debes completar el formulario del salvoconducto.")
            return redirect("core:cert_salvoconducto")
        return render(request, self.template_name, {"data": data})


@method_decorator(xframe_options_exempt, name="dispatch")
class SalvoconductoPdfView(LoginRequiredMixin, View):
    """
    Devuelve el PDF para el iframe (inline).
    """
    def get(self, request):
        data = request.session.get("salvoconducto_data")
        if not data:
            raise Http404("No hay datos de salvoconducto en la sesión.")

        pdf_bytes = build_salvoconducto_pdf(data)
        if not pdf_bytes:
            return render(
                request,
                "core/documents/salvoconducto_fallback.html",
                {"data": data},
            )

        return FileResponse(
            BytesIO(pdf_bytes),
            as_attachment=False,
            filename="salvoconducto_mudanza.pdf",
            content_type="application/pdf",
        )


class SalvoconductoDownloadView(LoginRequiredMixin, View):
    """
    Botón 'Descargar PDF'.
    """
    def get(self, request):
        data = request.session.get("salvoconducto_data")
        if not data:
            messages.warning(request, "Primero debes generar el salvoconducto.")
            return redirect("core:cert_salvoconducto")

        pdf_bytes = build_salvoconducto_pdf(data)
        if not pdf_bytes:
            messages.warning(
                request,
                "No se pudo generar el PDF en este momento.",
            )
            return redirect("core:cert_salvoconducto_preview")

        return FileResponse(
            BytesIO(pdf_bytes),
            as_attachment=True,
            filename="salvoconducto_mudanza.pdf",
            content_type="application/pdf",
        )


class SalvoconductoSendEmailView(LoginRequiredMixin, View):
    def get(self, request):
        data = request.session.get("salvoconducto_data")
        if not data:
            messages.warning(request, "Primero debes generar el salvoconducto.")
            return redirect("core:cert_salvoconducto")

        if not getattr(request.user, "email", None):
            messages.warning(request, "Tu usuario no tiene un correo configurado.")
            return redirect("core:cert_salvoconducto_preview")

        pdf_bytes = build_salvoconducto_pdf(data)
        if not pdf_bytes:
            messages.warning(
                request,
                "No se pudo generar el PDF para enviarlo por correo.",
            )
            return redirect("core:cert_salvoconducto_preview")

        # Nombre para el saludo
        nombre_saludo = (
            request.user.first_name
            or data.get("nombre")
            or request.user.username
        )

        # Formatear fecha de mudanza (puede venir como string "YYYY-MM-DD")
        fecha_raw = data.get("fecha_mudanza")
        fecha_mudanza_str = str(fecha_raw)
        try:
            from datetime import date
            año, mes, dia = map(int, str(fecha_raw).split("-"))
            fecha_mudanza_str = date(año, mes, dia).strftime("%d/%m/%Y")
        except Exception:
            pass

        cuerpo = (
            f"Estimado/a {nombre_saludo},\n\n"
            "Adjuntamos en este correo su Salvoconducto de Mudanza emitido por la "
            "Junta de Vecinos UT.\n\n"
            "Resumen de los datos registrados:\n"
            f" - Nombre completo    : {data.get('nombre')}\n"
            f" - RUT                : {data.get('rut')}\n"
            f" - Domicilio de origen: {data.get('domicilio_origen')}\n"
            f" - Domicilio de destino: {data.get('domicilio_destino')}\n"
            f" - Fecha de mudanza   : {fecha_mudanza_str}\n\n"
            "Este salvoconducto se emite para fines de control y traslado, y puede "
            "ser presentado ante la autoridad competente cuando sea requerido.\n\n"
            "Le recomendamos revisar que la información indicada sea correcta antes "
            "de utilizar el documento.\n\n"
            "Atentamente,\n"
            "Junta de Vecinos UT\n"
        )

        try:
            email = EmailMessage(
                subject="Salvoconducto de mudanza",
                body=cuerpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[request.user.email],
            )
            email.attach(
                "salvoconducto_mudanza.pdf",
                pdf_bytes,
                "application/pdf",
            )
            email.send(fail_silently=False)
            messages.success(request, "Enviamos el salvoconducto a tu correo.")
        except Exception as e:
            print("ERROR enviando salvoconducto:", e)
            messages.warning(
                request,
                "Hubo un problema al enviar el correo con el salvoconducto.",
            )

        return redirect("core:cert_salvoconducto_preview")



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

    - Delegado / Secretario / Presidente / Admin / superuser:
      pueden editar cualquier incidencia.
    - Tesorero / Vecino: solo pueden editar incidencias que ellos mismos reportaron.
    """

    permission_required = "core.change_incident"
    model = Incident
    form_class = IncidentResidentForm  # usamos el mismo formulario sencillo del vecino
    template_name = "core/incidents/form_resident.html"
    success_url = reverse_lazy("core:incident_mine")

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user

        # Moderadores (Admin / Secretario / Presidente / Delegado / superuser)
        if user_es_moderador_incidencias(u):
            return qs

        # Tesorero / Vecino / resto: solo incidencias propias
        return qs.filter(reportado_por=u)

    def form_valid(self, form):
        messages.success(self.request, "Incidencia actualizada correctamente.")
        return super().form_valid(form)


class IncidentDeleteView(
    NavItemsMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView
):
    """
    Eliminar incidencia desde 'Mis incidencias'.

    - Delegado / Secretario / Presidente / Admin / superuser:
      pueden borrar cualquier incidencia.
    - Tesorero / Vecino: solo pueden borrar incidencias que ellos mismos reportaron.
    """

    permission_required = "core.delete_incident"
    model = Incident
    template_name = "core/incidents/incident_confirm_delete.html"
    success_url = reverse_lazy("core:incident_mine")

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user

        # Moderadores de incidencias
        if user_es_moderador_incidencias(u):
            return qs

        # Tesorero / Vecino / resto: solo incidencias propias
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

        # NUEVO: solo Presidente y Tesorero ven el motivo de cancelación
        u = self.request.user
        groups = set(u.groups.values_list("name", flat=True))
        ctx["show_cancel_reason"] = "Presidente" in groups or "Tesorero" in groups

        return ctx

class ReservationCreateView(LoginRequiredMixin, CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = "core/reservations/form.html"

    # -----------------------------
    # 1) Leer el tipo desde la URL
    # -----------------------------
    def get_tipo_actual(self):
        """
        Devuelve el tipo actual según GET/POST:
        'cancha_futbol', 'cancha_basquet', 'cancha_padel' o 'salon'.
        """
        tipo = self.request.GET.get("tipo") or self.request.POST.get("tipo")
        validos = {"cancha_futbol", "cancha_basquet", "cancha_padel", "salon"}
        if tipo in validos:
            return tipo
        return "cancha_futbol"  # por defecto

    def get_initial(self):
        initial = super().get_initial()
        initial["tipo"] = self.get_tipo_actual()
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request   # 👈 para que el form lea GET (?tipo, ?resource, ?start_date)
        return kwargs

    # -----------------------------
    # 2) Crear reserva + Payment
    # -----------------------------
    def form_valid(self, form):
        user = self.request.user

        # 2.1 Ficha de vecino
        resident = Resident.objects.filter(user=user).first()
        if not resident:
            messages.error(self.request, "No se encontró tu ficha de vecino.")
            return redirect("core:reservation_mine")

        # 2.2 Bloquear si ya tiene una reserva con deuda pendiente
        tiene_deuda_reserva = Payment.objects.filter(
            resident=user,                         # Payment.resident es AUTH_USER_MODEL
            origin=Payment.ORIGIN_RESERVATION,
            status=Payment.STATUS_PENDING,
        ).exists()

        if tiene_deuda_reserva:
            messages.error(
                self.request,
                "Ya tienes una reserva pendiente. Debes pagar o cancelar esa "
                "reserva antes de crear una nueva.",
            )
            return redirect("core:reservation_mine")

        # 2.3 Guardar la reserva asociada al usuario y al vecino
        reservation = form.save(commit=False)
        reservation.requested_by = user
        reservation.resident = resident
        reservation.save()

        # 2.4 Crear el pago pendiente por la reserva
        Payment.create_for_reservation(reservation)

        messages.success(self.request, "Reserva creada correctamente.")
        return redirect("core:reservation_mine")

    def get_success_url(self):
        return reverse_lazy("core:reservation_mine")
    
class ReservationCancelView(LoginRequiredMixin, View):
    """
    Paso único: muestra un formulario para que el vecino indique
    el motivo de cancelación y, al confirmar, marca la reserva como
    CANCELLED y anula el pago pendiente asociado.
    """

    template_name = "core/reservations/cancel_form.html"

    def get_object(self, request, pk):
        # Solo puede cancelar sus propias reservas
        return get_object_or_404(
            Reservation,
            pk=pk,
            requested_by=request.user,
        )

    def get(self, request, pk):
        reserva = self.get_object(request, pk)

        if reserva.status != Reservation.Status.PENDING:
            messages.info(request, "Esta reserva ya no se puede cancelar.")
            return redirect("core:reservation_mine")

        form = ReservationCancelForm()
        contexto = {
            "reserva": reserva,
            "form": form,
        }
        return render(request, self.template_name, contexto)

    def post(self, request, pk):
        reserva = self.get_object(request, pk)

        if reserva.status != Reservation.Status.PENDING:
            messages.info(request, "Esta reserva ya no se puede cancelar.")
            return redirect("core:reservation_mine")

        form = ReservationCancelForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"reserva": reserva, "form": form},
            )

        motivo = form.cleaned_data["reason"].strip()

        # Actualizar reserva
        reserva.status = Reservation.Status.CANCELLED
        reserva.cancelled_at = timezone.now() if hasattr(reserva, "cancelled_at") else None
        reserva.cancel_reason = motivo
        reserva.save(update_fields=["status", "cancelled_at", "cancel_reason"])

        # Anular pago pendiente asociado a esa reserva (esto ya lo tenías)
        Payment.objects.filter(
            reservation=reserva,
            origin=Payment.ORIGIN_RESERVATION,
            status=Payment.STATUS_PENDING,
        ).update(status=Payment.STATUS_CANCELLED)

        messages.success(
            request,
            "Reserva cancelada, pago pendiente anulado y motivo registrado.",
        )
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

    def get_initial(self):
        """
        Si el usuario está autenticado y tiene email, lo prellenamos en el formulario.
        """
        initial = super().get_initial()
        u = self.request.user
        if u.is_authenticated and getattr(u, "email", ""):
            initial["email"] = u.email
        return initial

    def form_valid(self, form):
        if self.request.user.is_authenticated:
            form.instance.submitted_by = self.request.user
            if not form.instance.email and self.request.user.email:
                form.instance.email = self.request.user.email

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
        obj: InscriptionEvidence = self.get_object()
        status = form.cleaned_data["status"]
        role_code = form.cleaned_data.get("role") or None   # 👈 IMPORTANTE
        note = form.cleaned_data.get("note", "")

        if status == InscriptionEvidence.Status.APPROVED:
            obj.approve(user=self.request.user, note=note, role_code=role_code)
        elif status == InscriptionEvidence.Status.REJECTED:
            obj.reject(user=self.request.user, note=note)
        else:
            obj.status = InscriptionEvidence.Status.PENDING
            obj.validated_by = self.request.user
            obj.validated_at = timezone.now()
            obj.note = note
            obj.save()

        messages.success(self.request, "Inscripción actualizada.")
        return redirect("core:insc_admin")


