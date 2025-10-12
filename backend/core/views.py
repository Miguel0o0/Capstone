from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.utils.timezone import now
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import Announcement, Meeting, Minutes
from django.db.models import Q

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
        return u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()


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
    
# Permiso: Admin o Secretario
class IsAdminOrSecretaryMixin(UserPassesTestMixin):
    def test_func(self):
        u = self.request.user
        return u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()

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