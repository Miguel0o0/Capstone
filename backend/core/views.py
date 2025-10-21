from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.utils.timezone import now
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from .models import Announcement, Meeting, Minutes, Fee, Payment
from django.db.models import Q
from .forms import PaymentForm

# Create your views here.


def home(request):
    return render(request, "home.html")


@login_required
def dashboard(request):
    return render(request, "dashboard.html")


# --- Lectura (todos los autenticados) ---
class AnnouncementListView(LoginRequiredMixin, ListView):
    model = Announcement
    template_name = "core/announcement_list.html"
    context_object_name = "avisos"

    def get_queryset(self):
        qs = super().get_queryset()
        today = now().date()
        # Mostrar los avisos sin fecha de expiración o con fecha >= hoy
        return qs.filter(Q(visible_hasta__isnull=True) | Q(visible_hasta__gte=today))


class AnnouncementDetailView(LoginRequiredMixin, DetailView):
    model = Announcement
    template_name = "core/announcement_detail.html"
    context_object_name = "aviso"


# --- Helpers de permisos para CRUD ---
class IsAdminOrSecretaryMixin(UserPassesTestMixin):
    def test_func(self):
        u = self.request.user
        if not u.is_authenticated:
            return False
        # Permite superuser, o miembros de grupos Admin/Secretario
        return (
            u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
        )


# --- CRUD (solo Admin/Secretario) ---
class AnnouncementCreateView(LoginRequiredMixin, IsAdminOrSecretaryMixin, CreateView):
    model = Announcement
    fields = ["titulo", "cuerpo", "visible_hasta"]
    template_name = "core/announcement_form.html"
    success_url = reverse_lazy("core:announcement_list")

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        return super().form_valid(form)


class AnnouncementUpdateView(LoginRequiredMixin, IsAdminOrSecretaryMixin, UpdateView):
    model = Announcement
    fields = ["titulo", "cuerpo", "visible_hasta"]
    template_name = "core/announcement_form.html"
    success_url = reverse_lazy("core:announcement_list")


class AnnouncementDeleteView(LoginRequiredMixin, IsAdminOrSecretaryMixin, DeleteView):
    model = Announcement
    template_name = "core/announcement_confirm_delete.html"
    success_url = reverse_lazy("core:announcement_list")


class AdminOrSecretaryRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        u = self.request.user
        return u.is_authenticated and (
            u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
        )


# --- MEETINGS ---
class MeetingListView(LoginRequiredMixin, ListView):
    model = Meeting
    template_name = "core/meeting_list.html"
    context_object_name = "reuniones"


class MeetingDetailView(LoginRequiredMixin, DetailView):
    model = Meeting
    template_name = "core/meeting_detail.html"
    context_object_name = "reunion"


# (Opcional CRUD)
class MeetingCreateView(LoginRequiredMixin, IsAdminOrSecretaryMixin, CreateView):
    model = Meeting
    fields = ["fecha", "lugar", "tema"]
    template_name = "core/meeting_form.html"
    success_url = reverse_lazy("core:meeting_list")


class MeetingUpdateView(LoginRequiredMixin, IsAdminOrSecretaryMixin, UpdateView):
    model = Meeting
    fields = ["fecha", "lugar", "tema"]
    template_name = "core/meeting_form.html"
    success_url = reverse_lazy("core:meeting_list")


class MeetingDeleteView(LoginRequiredMixin, IsAdminOrSecretaryMixin, DeleteView):
    model = Meeting
    template_name = "core/meeting_confirm_delete.html"
    success_url = reverse_lazy("core:meeting_list")


# --- MINUTES (Acta) ---
class MinutesDetailView(LoginRequiredMixin, DetailView):
    model = Minutes
    template_name = "core/minutes_detail.html"
    context_object_name = "acta"


# (Opcional CRUD de actas)
class MinutesCreateView(LoginRequiredMixin, IsAdminOrSecretaryMixin, CreateView):
    model = Minutes
    fields = ["meeting", "texto", "archivo"]
    template_name = "core/minutes_form.html"
    success_url = reverse_lazy("core:meeting_list")


class MinutesUpdateView(LoginRequiredMixin, IsAdminOrSecretaryMixin, UpdateView):
    model = Minutes
    fields = ["meeting", "texto", "archivo"]
    template_name = "core/minutes_form.html"
    success_url = reverse_lazy("core:meeting_list")


class MinutesDeleteView(LoginRequiredMixin, IsAdminOrSecretaryMixin, DeleteView):
    model = Minutes
    template_name = "core/minutes_confirm_delete.html"
    success_url = reverse_lazy("core:meeting_list")


# ------- FEES (solo admin/secretario) -------


class FeeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Fee
    template_name = "core/fee_list.html"
    context_object_name = "fees"

    def test_func(self):
        u = self.request.user
        return (
            u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
        )


class FeeCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Fee
    fields = ("period", "amount")
    template_name = "core/fee_form.html"
    success_url = reverse_lazy("core:fee_list")

    def test_func(self):
        u = self.request.user
        return (
            u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
        )


class FeeUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Fee
    fields = ("period", "amount")
    template_name = "core/fee_form.html"
    success_url = reverse_lazy("core:fee_list")

    def test_func(self):
        u = self.request.user
        return (
            u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
        )


# ------- PAYMENTS ---------


class PaymentListAdminView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Payment
    template_name = "core/payment_list_admin.html"
    context_object_name = "payments"

    def test_func(self):
        u = self.request.user
        return (
            u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
        )

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


class MyPaymentsView(LoginRequiredMixin, ListView):
    """Vista 'Mis pagos' (solo ve los suyos)."""

    model = Payment
    template_name = "core/payment_list_mine.html"
    context_object_name = "payments"

    def get_queryset(self):
        return (
            Payment.objects.filter(resident=self.request.user)
            .select_related("fee")
            .order_by("-created_at")
        )


class PaymentCreateForResidentView(LoginRequiredMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = "core/payment_form.html"
    success_url = reverse_lazy("core:my_payments")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request  # <- IMPORTANTE
        return kwargs

    def form_valid(self, form):
        # Siempre es su propio pago
        form.instance.resident = self.request.user
        # Traemos el monto desde la cuota elegida
        form.instance.amount = form.cleaned_data["fee"].amount

        # Si es vecino, asegurar que quede "Pendiente"
        u = self.request.user
        is_admin = (
            u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
        )
        if not is_admin:
            form.instance.status = Payment.STATUS_PENDING

        return super().form_valid(form)


class PaymentUpdateAdminView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Payment
    form_class = PaymentForm
    template_name = "core/payment_form.html"

    def test_func(self):
        u = self.request.user
        return (
            u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = (
            self.request
        )  # <- por coherencia (aunque admin verá todas las opciones)
        return kwargs

    def get_success_url(self):
        return reverse_lazy("core:payment_list_admin")
