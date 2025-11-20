from datetime import datetime, timedelta, time as dtime

from django import forms
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm,AuthenticationForm
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.contrib.auth import get_user_model

from .models import (
    Announcement,
    Document,
    Fee,
    Incident,
    InscriptionEvidence,
    Meeting,
    Payment,
    Reservation,
    Resource,
)

_DT_FMT = "%Y-%m-%dT%H:%M"  # para <input type="datetime-local">

ROLE_CHOICES = [
    ("Vecino", "Vecino"),
    ("Delegado", "Delegado"),
    ("Tesorero", "Tesorero"),
    ("Secretario", "Secretario"),
    ("Presidente", "Presidente"),
]


# -------------------------------------------------
# ANUNCIOS
# -------------------------------------------------
class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ["titulo", "cuerpo", "visible_hasta", "importante"]
        widgets = {
            "visible_hasta": forms.DateInput(attrs={"type": "date"}),
        }


# -------------------------------------------------
# REUNIONES
# -------------------------------------------------
class MeetingForm(forms.ModelForm):
    """
    Formulario de reuniones con fecha + hora separadas
    (un input de calendario y otro de hora).
    """

    fecha = forms.SplitDateTimeField(
        widget=forms.SplitDateTimeWidget(
            date_attrs={"type": "date"},  # calendario
            time_attrs={"type": "time"},  # selector de hora
        ),
        label="Fecha y hora",
    )

    class Meta:
        model = Meeting
        fields = ["fecha", "lugar", "tema"]


# -------------------------------------------------
# PAGOS
# -------------------------------------------------
class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        # Simplificado para el vecino: solo elige la deuda pendiente
        fields = ["fee"]
        labels = {
            "fee": "Seleccionar deuda pendiente",
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


# ⬇⬇⬇ NUEVO FORMULARIO PARA TESORERO / ADMIN ⬇⬇⬇
class AdminPaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["resident", "fee", "amount", "status", "paid_at"]
        labels = {
            "resident": "Vecino / usuario",
            "fee": "Deuda",  # <-- aquí el cambio
            "amount": "Monto",
            "status": "Estado",
            "paid_at": "Fecha de pago",
        }
        widgets = {
            "paid_at": forms.DateInput(attrs={"type": "date"}),
        }


class PendingPaymentChoiceField(forms.ModelChoiceField):
    """
    Campo para elegir un Payment pendiente del usuario actual
    con una etiqueta legible en el combo.
    """

    def label_from_instance(self, obj: Payment) -> str:
        # Deuda por reserva
        if obj.origin == Payment.ORIGIN_RESERVATION and obj.reservation:
            recurso = (
                obj.reservation.resource.nombre
                if obj.reservation.resource
                else "Reserva"
            )
            fecha = (
                obj.reservation.start_at.strftime("%d/%m/%Y %H:%M")
                if obj.reservation.start_at
                else ""
            )
            return f"Reserva de {recurso} ({fecha}) - ${obj.amount}"

        # Deuda por cuota
        if obj.origin == Payment.ORIGIN_FEE and obj.fee:
            return f"{obj.fee.period} - ${obj.amount}"

        # Fallback genérico
        return f"${obj.amount} - {obj.get_status_display()}"


class ResidentPaymentStartForm(forms.Form):
    """
    Paso 1: el usuario elige uno de SUS pagos pendientes.
    No creamos un pago nuevo, solo seleccionamos uno existente.
    """

    payment = PendingPaymentChoiceField(
        label="Seleccionar pago pendiente",
        queryset=Payment.objects.none(),
        empty_label="Selecciona una deuda",
    )

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        qs = Payment.objects.filter(status=Payment.STATUS_PENDING)

        # Filtrar por el usuario actual
        if request is not None and request.user.is_authenticated:
            qs = qs.filter(resident=request.user)

        # Ordenar como quieras (últimos primero, por ejemplo)
        self.fields["payment"].queryset = qs.order_by("-created_at")
        
class PaymentReceiptUploadForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["receipt_file"]   # 👈 SOLO este campo, nada de receipt_note

        widgets = {
            "receipt_file": forms.ClearableFileInput(attrs={"class": "input"}),
        }
        labels = {
            "receipt_file": "Comprobante de transferencia",
        }
        help_texts = {
            "receipt_file": "Sube el comprobante de la transferencia (PDF/JPG/PNG).",
        }

class PaymentReviewForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["status", "review_comment"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].label = "Estado del pago"
        self.fields["review_comment"].label = "Comentario para el vecino"
        self.fields["review_comment"].required = False

        
class PaymentReceiptForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["receipt_file"]
        labels = {
            "receipt_file": "Comprobante de transferencia",
        }



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

    # Campos extra: fecha y hora separadas
    start_date = forms.DateField(
        label="Fecha", widget=forms.DateInput(attrs={"type": "date"})
    )
    # 👇 AHORA ES UN SELECT DE HORAS
    start_time = forms.ChoiceField(
        label="Hora",
        choices=[],              # se rellenan en __init__
        widget=forms.Select,
    )

    class Meta:
        model = Reservation
        fields = ["tipo", "resource", "title", "start_date", "start_time", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "resource": "Recurso",
            "title": "Título/uso",
            "notes": "Notas",
        }

    def __init__(self, *args, **kwargs):
        # Si pasas request desde la vista, la usamos para leer ?tipo=..., ?resource=..., ?start_date=...
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # --- Tipo seleccionado ---
        if self.data.get("tipo"):
            selected_tipo = self.data.get("tipo")
        elif self.request and self.request.GET.get("tipo"):
            selected_tipo = self.request.GET.get("tipo")
        else:
            selected_tipo = self.initial.get("tipo") or self.TIPO_CHOICES[0][0]
        self.fields["tipo"].initial = selected_tipo

        # --- Fecha seleccionada (para disponibilidad) ---
        selected_date = None
        raw_date = None

        if self.is_bound:
            raw_date = self.data.get("start_date") or self.initial.get("start_date")
        elif self.request and self.request.GET.get("start_date"):
            raw_date = self.request.GET.get("start_date")
        else:
            raw_date = self.initial.get("start_date")

        if isinstance(raw_date, datetime):
            selected_date = raw_date.date()
        elif hasattr(raw_date, "year"):
            selected_date = raw_date
        elif raw_date:
            try:
                selected_date = datetime.strptime(str(raw_date), "%Y-%m-%d").date()
            except Exception:
                selected_date = None

        # Si no hay fecha aún, proponemos hoy
        if not selected_date:
            selected_date = datetime.now().date()
        self.fields["start_date"].initial = selected_date

        # --- Recursos activos filtrados por tipo ---
        base_qs = Resource.objects.filter(activo=True).order_by("nombre")

        if selected_tipo == "salon":
            salon_qs = base_qs.filter(
                Q(nombre__icontains="salon") | Q(nombre__icontains="salón")
            )
            self.fields["resource"].queryset = salon_qs
            self.fields["resource"].widget = forms.HiddenInput()

            salon = salon_qs.first()
            if salon:
                self.fields["resource"].initial = salon.pk

            self.fields["title"].required = False
            self.fields["notes"].required = False

        elif selected_tipo == "cancha_futbol":
            canchas_qs = base_qs.filter(
                Q(nombre__icontains="futbol") | Q(nombre__icontains="fútbol")
            )
            self.fields["resource"].queryset = canchas_qs
            self.fields["resource"].empty_label = "— Selecciona una cancha —"
            self.fields["resource"].label = "Cancha de fútbol"
            self.fields["title"].required = False
            self.fields["notes"].required = False

        elif selected_tipo == "cancha_basquet":
            canchas_qs = base_qs.filter(
                Q(nombre__icontains="basquet") | Q(nombre__icontains="básquet")
            )
            self.fields["resource"].queryset = canchas_qs
            self.fields["resource"].empty_label = "— Selecciona una cancha —"
            self.fields["resource"].label = "Cancha de básquetbol"
            self.fields["title"].required = False
            self.fields["notes"].required = False

        elif selected_tipo == "cancha_padel":
            canchas_qs = base_qs.filter(nombre__icontains="padel")
            self.fields["resource"].queryset = canchas_qs
            self.fields["resource"].empty_label = "— Selecciona una cancha —"
            self.fields["resource"].label = "Cancha de pádel"
            self.fields["title"].required = False
            self.fields["notes"].required = False

        else:
            canchas_qs = base_qs.exclude(
                Q(nombre__icontains="salon") | Q(nombre__icontains="salón")
            )
            self.fields["resource"].queryset = canchas_qs
            self.fields["resource"].empty_label = "— Selecciona una cancha —"
            self.fields["resource"].label = "Cancha número"
            self.fields["title"].required = False
            self.fields["notes"].required = False

        # --- Recurso seleccionado (para disponibilidad) ---
        selected_resource_id = None
        if self.is_bound:
            selected_resource_id = (
                self.data.get("resource") or self.initial.get("resource")
            )
        else:
            if self.request and self.request.GET.get("resource"):
                selected_resource_id = self.request.GET.get("resource")
            else:
                selected_resource_id = self.initial.get("resource")
                    # Marcar el recurso seleccionado como initial,
        # para que el <select> lo muestre después de recargar.
        if selected_resource_id:
            self.fields["resource"].initial = selected_resource_id


        # --- Calcular horas ocupadas para ese recurso + fecha ---
        busy = []
        if selected_resource_id and selected_date:
            reservas = Reservation.objects.filter(
                resource_id=selected_resource_id,
                status__in=[
                    Reservation.Status.PENDING,
                    Reservation.Status.APPROVED,
                ],
                start_at__date=selected_date,
            )
            busy = [f"{r.start_at.hour:02d}:00" for r in reservas]

        self.busy_hours = busy  # lo usamos en el template

        # --- Construir choices de hora: de 10:00 a 23:00 ---
        hour_choices = []
        for h in range(10, 24):
            label = f"{h:02d}:00"
            hour_choices.append((label, label))
        self.fields["start_time"].choices = hour_choices

        # Hora por defecto: primera hora libre
        if not self.is_bound:
            initial_time = None
            for value, _label in hour_choices:
                if value not in busy:
                    initial_time = value
                    break
            if initial_time:
                self.fields["start_time"].initial = initial_time

    def clean(self):
        cleaned = super().clean()
        resource = cleaned.get("resource")
        tipo = cleaned.get("tipo")
        title = (cleaned.get("title") or "").strip()
        notes = (cleaned.get("notes") or "").strip()

        # Combinar fecha + hora -> start_at / end_at (1 hora)
        start_date = cleaned.get("start_date")
        start_time_str = cleaned.get("start_time")

        if start_date and start_time_str:
            try:
                h, m = map(int, str(start_time_str).split(":"))
            except ValueError:
                raise ValidationError("Hora de reserva inválida.")
            start_dt = datetime.combine(start_date, dtime(hour=h, minute=m))
            end_dt = start_dt + timedelta(hours=1)

            cleaned["start_at"] = start_dt
            cleaned["end_at"] = end_dt
            self.instance.start_at = start_dt
            self.instance.end_at = end_dt
        else:
            raise ValidationError("Debes indicar fecha y hora de la reserva.")

        # Reglas especiales para salón
        if tipo == "salon":
            if len(title) < 3:
                self.add_error("title", "Indica un título corto del evento.")
            if len(notes) < 10:
                self.add_error(
                    "notes",
                    "Describe brevemente el tipo de evento (mín. 10 caracteres).",
                )

            if not resource:
                salon = (
                    Resource.objects.filter(activo=True)
                    .filter(Q(nombre__icontains="salon") | Q(nombre__icontains="salón"))
                    .first()
                )
                if salon:
                    cleaned["resource"] = salon
                    self.instance.resource = salon
            else:
                self.instance.resource = resource

        else:
            if resource:
                self.instance.resource = resource

            if not title:
                if resource:
                    auto_title = f"Uso {resource.nombre}"
                else:
                    auto_title = "Reserva de cancha"
                cleaned["title"] = auto_title
                self.instance.title = auto_title
            else:
                self.instance.title = title

        # Validar solape (doble check, por si acaso)
        start = cleaned.get("start_at")
        end = cleaned.get("end_at")
        resource = cleaned.get("resource") or self.instance.resource
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

    def save(self, commit=True):
        """
        Asigna start_at y end_at en la instancia del modelo
        usando start_date + start_time antes de guardar.
        """
        instance = super().save(commit=False)

        start_date = self.cleaned_data.get("start_date")
        start_time_str = self.cleaned_data.get("start_time")
        if start_date and start_time_str:
            h, m = map(int, str(start_time_str).split(":"))
            start_dt = datetime.combine(start_date, dtime(hour=h, minute=m))
            instance.start_at = start_dt
            instance.end_at = start_dt + timedelta(hours=1)

        if commit:
            instance.save()

        return instance

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

class ReservationCancelForm(forms.Form):
    reason = forms.CharField(
        label="Motivo de la cancelación",
        required=True,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Ej: No podré asistir, cambio de planes, etc.",
            }
        ),
        max_length=500,
    )

# --------------------------------------------------
# INSCRIPCIONES – formulario público (anónimo)
# --------------------------------------------------
class InscriptionCreateForm(forms.ModelForm):
    class Meta:
        model = InscriptionEvidence
        fields = ["first_name", "last_name", "rut", "address", "email", "file"]

        labels = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "rut": "RUT",
            "address": "Dirección",
            "email": "Correo electrónico",
            "file": "Boleta de servicio",
        }

        widgets = {
            "first_name": forms.TextInput(
                attrs={"placeholder": "Tu nombre"}
            ),
            "last_name": forms.TextInput(
                attrs={"placeholder": "Tu apellido"}
            ),
            "rut": forms.TextInput(
                attrs={"placeholder": "12.345.678-9"}
            ),
            "address": forms.TextInput(
                attrs={"placeholder": "Calle, número, depto, etc."}
            ),
            "email": forms.EmailInput(
                attrs={"placeholder": "tucorreo@ejemplo.com"}
            ),
        }

        help_texts = {
            "rut": "Ingresa tu RUT con o sin puntos, incluyendo el dígito verificador.",
            "email": (
                "Usaremos este correo para avisarte si tu inscripción "
                "fue aprobada o rechazada."
            ),
            "file": "Sube una boleta de agua, luz o gas en PDF/JPG/PNG (máx. 5 MB).",
        }



# --------------------------------------------------
# INSCRIPCIONES – formulario de gestión (admin)
# --------------------------------------------------
# Opciones de rol que verá el presidente/secretario al aprobar


class InscriptionManageForm(forms.ModelForm):
    # Campo extra, NO es del modelo: solo sirve para decidir a qué grupo va
    role = forms.ChoiceField(
        label="Rol",
        choices=[("", "---------")] + ROLE_CHOICES,  # primera opción vacía
        required=False,
        widget=forms.Select,
    )

    class Meta:
        model = InscriptionEvidence
        fields = ["status", "role", "note"]  # ya no usamos resident
        widgets = {
            "status": forms.Select,
            "note": forms.Textarea(attrs={"rows": 4}),
        }

User = get_user_model()


class JuntaPasswordResetForm(PasswordResetForm):
    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not User.objects.filter(email__iexact=email, is_active=True).exists():
            raise forms.ValidationError(
                "No existe ninguna cuenta registrada con este correo."
            )
        return email


class JuntaSetPasswordForm(SetPasswordForm):
    """
    Formulario para definir nueva contraseña con mensajes en español.
    """
    error_messages = {
        **SetPasswordForm.error_messages,
        "password_mismatch": "Las dos contraseñas no coinciden.",
    }

class JuntaAuthenticationForm(AuthenticationForm):
    """
    Formulario de login con mensajes de error en español.
    """
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": (
            "Usuario o contraseña incorrectos. "
            "Por favor, verifica tus datos e inténtalo nuevamente."
        ),
        "inactive": "Esta cuenta está desactivada.",
    }


class JuntaPasswordResetForm(PasswordResetForm):
    """
    Formulario de 'olvidé mi contraseña' con validación
    de que el correo exista.
    """
    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not User.objects.filter(email__iexact=email, is_active=True).exists():
            raise forms.ValidationError(
                "No existe ninguna cuenta registrada con este correo."
            )
        return email


class JuntaSetPasswordForm(SetPasswordForm):
    """
    Formulario para definir nueva contraseña con mensajes en español.
    """
    error_messages = {
        **SetPasswordForm.error_messages,
        "password_mismatch": "Las dos contraseñas no coinciden.",
    }