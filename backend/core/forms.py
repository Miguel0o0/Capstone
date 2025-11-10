from django import forms

from .models import Document, Fee, Incident, Payment, Reservation, Resource


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["resident", "fee", "status", "paid_at"]
        widgets = {
            "paid_at": forms.DateInput(attrs={"type": "date"}),
        }

        labels = {
            "resident": "Vecino",
            "fee": "Cuota",
            "status": "Estado",
            "paid_at": "Fecha de pago",
        }

    def __init__(self, *args, **kwargs):
        # recibimos la request para saber el rol
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # ordenar cuotas como prefieras
        self.fields["fee"].queryset = Fee.objects.all().order_by("-id")

        # Si es vecino (no admin/secretario), escondemos 'resident'
        # y limitamos 'status' solo a "Pendiente".
        if self.request:
            u = self.request.user
            is_admin = (
                u.is_superuser
                or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
            )

            if not is_admin:
                # vecino: no puede elegir otro residente
                self.fields["resident"].initial = u
                self.fields["resident"].widget = forms.HiddenInput()

                # vecino: no puede marcar pagado
                # (usa las constantes del modelo Payment)
                label_map = dict(Payment.STATUS_CHOICES)
                self.fields["status"].choices = [
                    (Payment.STATUS_PENDING, label_map[Payment.STATUS_PENDING])
                ]


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["titulo", "descripcion", "categoria", "visibilidad", "archivo"]


class IncidentForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = ["categoria", "titulo", "descripcion", "foto"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
        }


class IncidentManageForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = ["status", "asignada_a", "nota_resolucion"]
        widgets = {
            "nota_resolucion": forms.Textarea(attrs={"rows": 4}),
        }


_DT_FMT = "%Y-%m-%dT%H:%M"  # para <input type="datetime-local">


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ["resource", "title", "start_at", "end_at", "notes"]
        widgets = {
            "start_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format=_DT_FMT
            ),
            "end_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format=_DT_FMT
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # solo recursos activos, ordenados
        self.fields["resource"].queryset = Resource.objects.filter(
            activo=True
        ).order_by("nombre")


class ReservationManageForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ["status", "start_at", "end_at", "notes"]
        widgets = {
            "start_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format=_DT_FMT
            ),
            "end_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format=_DT_FMT
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_at"].input_formats = [_DT_FMT]
        self.fields["end_at"].input_formats = [_DT_FMT]
