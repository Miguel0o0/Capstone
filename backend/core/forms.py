from datetime import datetime, timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import (
    Document,
    Fee,
    Incident,
    InscriptionEvidence,
    Payment,
    Reservation,
    Resource,
)

_DT_FMT = "%Y-%m-%dT%H:%M"  # para <input type="datetime-local">


# -------------------------------------------------
# PAGOS
# -------------------------------------------------
class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        # Simplificado para el vecino: solo elige la cuota/pago pendiente
        fields = ["fee"]
        labels = {
            "fee": "Seleccionar pago pendiente",
        }
        widgets = {}

    def __init__(self, *args, **kwargs):
        # recibimos la request para saber el rol
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Mostrar cuotas en el orden que prefieras
        qs = Fee.objects.all().order_by("-id")

        if self.request and self.request.user.is_authenticated:
            u = self.request.user
            is_admin = (
                u.is_superuser
                or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
            )

            if not is_admin:
                # Vecino: solo cuotas que AÚN no estén pagadas por él
                # OJO: el lookup correcto es "payments__" (plural)
                qs = qs.exclude(
                    payments__resident=u,
                    payments__status=Payment.STATUS_PAID,
                ).distinct()

        self.fields["fee"].queryset = qs


class ResidentPaymentStartForm(forms.ModelForm):
    """
    Formulario mínimo para el vecino en el Paso 1 del pago:
    solo seleccionar una deuda pendiente (Fee sin Payment PAID del usuario).
    """

    class Meta:
        model = Payment
        fields = ["fee"]
        labels = {"fee": "Seleccionar deuda pendiente"}

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        user = getattr(request, "user", None)
        qs = Fee.objects.all()

        if user and user.is_authenticated:
            # Mostrar fees que NO tienen un pago marcado como PAID por este usuario
            qs = qs.exclude(
                payments__resident=user,
                payments__status=Payment.STATUS_PAID,
            )

        self.fields["fee"].queryset = qs.order_by("-id")
        self.fields["fee"].empty_label = "— Selecciona una deuda —"


# -------------------------------------------------
# DOCUMENTOS
# -------------------------------------------------
class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["titulo", "descripcion", "categoria", "visibilidad", "archivo"]


# -------------------------------------------------
# INCIDENCIAS
# -------------------------------------------------
class IncidentForm(forms.ModelForm):
    """
    Form usado por administración para gestionar incidencias completas
    (con categoría, etc.). Se mantiene como lo tenías.
    """

    class Meta:
        model = Incident
        fields = ["categoria", "titulo", "descripcion", "foto"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
        }


class IncidentResidentForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = ["titulo", "descripcion", "foto"]  # sin categoría
        labels = {
            "titulo": "Título de la incidencia",
            "descripcion": "Detalle",
            "foto": "Foto (opcional)",
        }
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Habilitar cámara en móviles cuando el navegador lo soporte
        if "foto" in self.fields:
            self.fields["foto"].widget.attrs.update(
                {"accept": "image/*", "capture": "environment"}
            )


class IncidentManageForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = ["status", "asignada_a", "nota_resolucion"]
        widgets = {
            "nota_resolucion": forms.Textarea(attrs={"rows": 4}),
        }


# -------------------------------------------------
# RESERVAS
# -------------------------------------------------
_DT_FMT = "%Y-%m-%dT%H:%M"  # para <input type="datetime-local">


class ReservationForm(forms.ModelForm):
    # Campo extra: tipo de reserva
    TIPO_CHOICES = [
        ("cancha_futbol", "Cancha de fútbol"),
        ("cancha_basquet", "Cancha de básquetbol"),
        ("cancha_padel", "Cancha de pádel"),
        ("salon", "Salón de eventos"),
    ]
    tipo = forms.ChoiceField(choices=TIPO_CHOICES, label="¿Qué deseas reservar?")

    # Campos extra: fecha y hora separadas (más simple para el vecino)
    start_date = forms.DateField(
        label="Fecha", widget=forms.DateInput(attrs={"type": "date"})
    )
    start_time = forms.TimeField(
        label="Hora", widget=forms.TimeInput(attrs={"type": "time"})
    )

    class Meta:
        model = Reservation
        fields = ["tipo", "resource", "title", "start_date", "start_time", "notes"]
        widgets = {
            # start_at/end_at del modelo NO van en el form; los construimos en clean()
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "resource": "Recurso",
            "title": "Título/uso",
            "notes": "Notas",
        }

    def __init__(self, *args, **kwargs):
        # Si pasas request desde la vista, la usamos para leer ?tipo=...
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # defaults de fecha/hora
        now_dt = datetime.now().replace(second=0, microsecond=0)
        self.fields["start_date"].initial = now_dt.date()
        self.fields["start_time"].initial = now_dt.time()

        # detectar tipo seleccionado (POST > GET > initial > primera opción)
        if self.data.get("tipo"):
            selected_tipo = self.data.get("tipo")
        elif self.request and self.request.GET.get("tipo"):
            selected_tipo = self.request.GET.get("tipo")
        else:
            selected_tipo = self.initial.get("tipo") or self.TIPO_CHOICES[0][0]
        self.fields["tipo"].initial = selected_tipo

        # queryset base de recursos activos
        base_qs = Resource.objects.filter(activo=True).order_by("nombre")

        if selected_tipo == "salon":
            # FILTRA salón y OCULTA el combo de resource
            salon_qs = base_qs.filter(
                Q(nombre__icontains="salon") | Q(nombre__icontains="salón")
            )
            self.fields["resource"].queryset = salon_qs
            self.fields["resource"].widget = forms.HiddenInput()

            salon = salon_qs.first()
            if salon:
                self.fields["resource"].initial = salon.pk

            # Para salón, título/notas NO obligatorias aquí (se validan en clean())
            self.fields["title"].required = False
            self.fields["notes"].required = False

        else:
            # CANCHAS: por mientras mostramos solo las "disponibles" (ej.: 2 y 4)
            # TODO: reemplazar por disponibilidad real contra la tabla Reservation
            canchas_qs = base_qs.filter(nombre__icontains="cancha").filter(
                Q(nombre__icontains=" 2")
                | Q(nombre__icontains=" 4")
                | Q(nombre__icontains="2 ")
                | Q(nombre__icontains="4 ")
            )
            self.fields["resource"].queryset = canchas_qs
            self.fields["resource"].empty_label = "— Selecciona una cancha —"
            self.fields["resource"].label = "Cancha número"

            # No exigimos título/nota en canchas
            self.fields["title"].required = False
            self.fields["notes"].required = False

    def clean(self):
        cleaned = super().clean()
        resource = cleaned.get("resource")
        tipo = cleaned.get("tipo")
        title = (cleaned.get("title") or "").strip()
        notes = (cleaned.get("notes") or "").strip()

        # Combinar fecha + hora -> start_at / end_at (1 hora por defecto)
        start_date = cleaned.get("start_date")
        start_time = cleaned.get("start_time")
        if start_date and start_time:
            start_dt = datetime.combine(start_date, start_time)
            cleaned["start_at"] = start_dt
            cleaned["end_at"] = start_dt + timedelta(hours=1)
        else:
            raise ValidationError("Debes indicar fecha y hora de la reserva.")

        # Si es salón, exigimos título y descripción mínima
        if tipo == "salon":
            if len(title) < 3:
                self.add_error("title", "Indica un título corto del evento.")
            if len(notes) < 10:
                self.add_error(
                    "notes",
                    "Describe brevemente el tipo de evento (mín. 10 caracteres).",
                )

            # Si ocultamos resource y no llegó, auto-asignar el primer salón
            if not resource:
                salon = (
                    Resource.objects.filter(activo=True)
                    .filter(Q(nombre__icontains="salon") | Q(nombre__icontains="salón"))
                    .first()
                )
                if salon:
                    cleaned["resource"] = salon

        # Validar solape (disponibilidad real)
        start = cleaned.get("start_at")
        end = cleaned.get("end_at")
        resource = cleaned.get("resource")
        if resource and start and end:
            conflict = Reservation.objects.filter(
                resource=resource,
                status__in=[Reservation.Status.PENDING, Reservation.Status.APPROVED],
                start_at__lt=end,
                end_at__gt=start,
            ).exists()
            if conflict:
                raise ValidationError(
                    "Ese horario ya está reservado para el recurso elegido. "
                    "Elige otro horario o recurso."
                )

        return cleaned


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


# -------------------------------------------------
# INSCRIPCIONES
# -------------------------------------------------
class InscriptionCreateForm(forms.ModelForm):
    class Meta:
        model = InscriptionEvidence
        fields = ["file"]
        widgets = {
            "file": forms.ClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png"})
        }


class InscriptionManageForm(forms.ModelForm):
    class Meta:
        model = InscriptionEvidence
        fields = ["status", "resident", "note"]
