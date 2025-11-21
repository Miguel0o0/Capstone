# backend/core/models.py
import os
import uuid
import secrets
import string


from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth.models import Group

User = get_user_model()

ALLOWED_EXTS = {"pdf", "jpg", "jpeg", "png"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


class Resident(models.Model):
    """
    Perfil extendido del usuario (opcional).
    Si no hay User (anónimo / aún sin cuenta), igual podemos registrar al residente.
    """

    user = models.OneToOneField(
        User,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="resident_profile",
    )
    nombre = models.CharField(max_length=120)
    email = models.EmailField(blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    activo = models.BooleanField(default=True)
    rut = models.CharField("RUT", max_length=12, blank=True, null=True, unique=True)

    class Meta:
        ordering = ["nombre"]  # listado alfabético por nombre

    def __str__(self):
        return self.nombre


class Household(models.Model):
    """
    Vivienda/Unidad. Puede tener varios residentes (comparten hogar).
    """

    direccion = models.CharField(max_length=200)
    numero = models.CharField(max_length=20, blank=True)
    referencia = models.CharField(max_length=200, blank=True)

    # Relación muchos-a-muchos con Resident
    residents = models.ManyToManyField(
        Resident,
        related_name="households",
        blank=True,
    )

    def __str__(self):
        # algo legible en admin/listas
        return f"{self.direccion} {self.numero}".strip()

class Announcement(models.Model):
    titulo = models.CharField(max_length=200)
    cuerpo = models.TextField()
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
    )
    visible_hasta = models.DateField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    # NUEVO: flag para destacar avisos
    importante = models.BooleanField(
        "Marcar como importante",
        default=False,
        help_text="Si está activo, este aviso se destacará para los vecinos.",
    )

    class Meta:
        ordering = ["-creado_en"]  # sigue ordenado por fecha de publicación

    def __str__(self):
        return self.titulo

class Meeting(models.Model):
    fecha = models.DateTimeField()
    lugar = models.CharField(max_length=200)
    tema = models.CharField(max_length=200)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        # Ej.: "Reunión 2025-10-12 19:00 — Sede vecinal"
        return f"Reunión {self.fecha:%Y-%m-%d %H:%M} — {self.lugar}"


class Minutes(models.Model):
    meeting = models.OneToOneField(
        Meeting, on_delete=models.CASCADE, related_name="minutes"
    )
    texto = models.TextField()
    archivo = models.FileField(upload_to="actas/", blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Acta de {self.meeting.fecha:%Y-%m-%d}"


# Constantes de estado (a nivel de módulo):
STATUS_PENDING = "pending"
STATUS_PAID = "paid"
STATUS_CHOICES = [
    (STATUS_PENDING, "Pendiente"),
    (STATUS_PAID, "Pagado"),
]


class Fee(models.Model):
    period = models.CharField(
        "Nombre de deuda",
        max_length=100,
        help_text="Ej: Cancha fútbol 1, Cancha básquet 2, Cancha pádel 1, etc.",
    )

    # <- ahora el monto es OPCIONAL y pensado como sugerido
    amount = models.DecimalField(
        "Monto sugerido",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "Deuda"
        verbose_name_plural = "Deudas"

    def __str__(self):
        # Si no quieres que salga el monto en el combo, deja sólo el nombre:
        return self.period
        # (si algún día quieres mostrar también el monto sugerido:
        # return f"{self.period} (${self.amount})" if self.amount is not None else self.period


class Payment(models.Model):
    # --------- Estados ----------
    STATUS_PENDING = "pending"                # deuda creada, sin comprobante
    STATUS_PENDING_REVIEW = "pending_review"  # vecino subió comprobante, tesorero debe revisar
    STATUS_PAID = "paid"                      # pago aceptado
    STATUS_CANCELLED = "cancelled"            # pago anulado (p.ej. reserva cancelada)

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pendiente"),
        (STATUS_PENDING_REVIEW, "Pendiente de revisión"),
        (STATUS_PAID, "Pagado"),
        (STATUS_CANCELLED, "Cancelado"),
    )

    # --------- Origen ----------
    ORIGIN_FEE = "fee"                  # cuota normal
    ORIGIN_RESERVATION = "reservation"  # deuda por reserva

    ORIGIN_CHOICES = (
        (ORIGIN_FEE, "Cuota"),
        (ORIGIN_RESERVATION, "Reserva"),
    )

    # --- Campos principales ---

    resident = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="Residente",
    )

    fee = models.ForeignKey(
        "Fee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name="Cuota",
    )

    reservation = models.ForeignKey(
        "Reservation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name="Reserva",
    )

    amount = models.DecimalField(
        "Monto",
        max_digits=9,
        decimal_places=2,
    )

    status = models.CharField(
        "Estado",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    origin = models.CharField(
        "Origen",
        max_length=20,
        choices=ORIGIN_CHOICES,
        default=ORIGIN_RESERVATION,
    )

    # --------- Comprobante (vecino) ----------
    receipt_file = models.FileField(
        "Comprobante",
        upload_to="payment_receipts/",
        null=True,
        blank=True,
    )
    receipt_uploaded_at = models.DateTimeField(
        "Comprobante subido en",
        null=True,
        blank=True,
    )

    # --------- Revisión (tesorero/presidente) ----------
    review_comment = models.TextField(
        "Comentario para el vecino",
        null=True,
        blank=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments_reviewed",
        verbose_name="Revisado por",
    )
    reviewed_at = models.DateTimeField(
        "Revisado en",
        null=True,
        blank=True,
    )

    # --------- Fechas ---------
    paid_at = models.DateTimeField(
        "Fecha de pago",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        "Creado en",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        constraints = [
            models.UniqueConstraint(
                fields=["resident", "fee", "origin"],
                condition=Q(origin="fee"),
                name="unique_fee_payment_per_resident",
            )
        ]
        ordering = ["-created_at"]

    # -------- Helpers --------

    @classmethod
    def create_for_reservation(cls, reservation, amount=None):
        """
        Crea un Payment PENDING asociado a una reserva.
        """
        resource = reservation.resource
        if not resource or not resource.requiere_pago():
            return None

        if amount is None:
            amount = resource.precio_por_hora

        return cls.objects.create(
            resident=reservation.requested_by,
            reservation=reservation,
            fee=None,
            amount=amount,
            status=cls.STATUS_PENDING,
            origin=cls.ORIGIN_RESERVATION,
        )

    def __str__(self):
        base_status = dict(self.STATUS_CHOICES).get(self.status, self.status)
        if self.origin == self.ORIGIN_RESERVATION and self.reservation:
            return f"{self.resident} → Reserva #{self.reservation.id} ({base_status})"
        if self.origin == self.ORIGIN_FEE and self.fee:
            return f"{self.resident} → {self.fee} ({base_status})"
        return f"{self.resident} → {self.amount} ({base_status})"

# -----------------------------
# Documentos (version completa)
# -----------------------------

# --- Helpers y validadores ---
ALLOWED_EXTENSIONS = [
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "csv",
    "ppt",
    "pptx",
    "jpg",
    "jpeg",
    "png",
]
MAX_FILE_MB = 20


def validate_file_size(f):
    max_bytes = MAX_FILE_MB * 1024 * 1024
    if f.size > max_bytes:
        raise ValidationError(f"El archivo supera {MAX_FILE_MB} MB.")


def document_upload_to(instance, filename):
    # Nombre único y carpeta por año/mes (si created_at aún no existe, usamos ahora)
    ext = filename.rsplit(".", 1)[-1].lower()
    uid = uuid.uuid4().hex
    dt = getattr(instance, "created_at", None) or timezone.now()
    return os.path.join("documentos", f"{dt:%Y/%m}", f"{uid}.{ext}")


class DocumentCategory(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = "Categoría de documento"
        verbose_name_plural = "Categorías de documentos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Document(models.Model):
    class Visibility(models.TextChoices):
        PUBLICO = "PUBLICO", "Público"
        RESIDENTES = "RESIDENTES", "Sólo residentes"
        STAFF = "STAFF", "Sólo staff (Admin/Secretario)"

    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    categoria = models.ForeignKey(
        DocumentCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos",
    )
    archivo = models.FileField(
        upload_to=document_upload_to,
        validators=[FileExtensionValidator(ALLOWED_EXTENSIONS), validate_file_size],
    )
    visibilidad = models.CharField(
        max_length=12, choices=Visibility.choices, default=Visibility.RESIDENTES
    )
    subido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_subidos",
    )
    is_active = models.BooleanField(default=True)  # “Soft delete”
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["visibilidad"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(titulo__regex=r".*\S.*"), name="document_title_not_blank"
            )
        ]

    def __str__(self):
        return self.titulo

    @property
    def filename(self):
        return os.path.basename(self.archivo.name)


def validate_image_size(f):
    max_mb = 10
    if f.size > max_mb * 1024 * 1024:
        raise ValidationError(f"La imagen supera {max_mb} MB.")


def incident_upload_to(instance, filename):
    """
    Ruta para las fotos de incidencias.

    No depende de created_at (que todavía es None cuando se crea).
    Usa:
      - id del usuario que reporta (o 'anon' si no hay)
      - fecha/hora actual
      - un uuid para evitar colisiones
    """
    # extensión del archivo
    ext = (filename.rsplit(".", 1)[-1] or "").lower()

    # id del usuario que reporta, o 'anon' como fallback
    user_id = getattr(getattr(instance, "reportado_por", None), "id", "anon")

    # fecha/hora actual
    dt = timezone.now()

    # nombre de archivo único
    new_name = f"{dt:%Y%m%d_%H%M%S}_{uuid.uuid4().hex}.{ext}"

    # quedaría algo como: incidencias/3/20251112_221800_abcd1234.jpg
    return os.path.join("incidencias", str(user_id), new_name)


class IncidentCategory(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Categoría de incidencia"
        verbose_name_plural = "Categorías de incidencias"

    def __str__(self):
        return self.nombre


class Incident(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Abierta"
        IN_PROGRESS = "IN_PROGRESS", "En progreso"
        RESOLVED = "RESOLVED", "Resuelta"
        REJECTED = "REJECTED", "Rechazada"

    reportado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="incidencias_reportadas",
    )
    categoria = models.ForeignKey(
        IncidentCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidencias",
    )
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    foto = models.ImageField(
        upload_to=incident_upload_to,
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png"]),
            validate_image_size,
        ],
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    asignada_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidencias_asignadas",
        help_text="(Opcional) Miembro del staff que gestionará la incidencia",
    )
    nota_resolucion = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]
        verbose_name = "Incidencia"
        verbose_name_plural = "Incidencias"

    def __str__(self):
        # Ya no usamos esto en la lista, pero lo dejo por si lo ves en admin
        return f"[{self.get_status_display()}] {self.titulo}"


class ResourceCategory(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Categoría de recurso"
        verbose_name_plural = "Categorías de recursos"

    def __str__(self):
        return self.nombre


class Resource(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    categoria = models.ForeignKey(
        ResourceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recursos",
    )
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    # (Opcional para el futuro) horarios hábiles
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)

    # Precio por hora para canchas u otros recursos de pago
    precio_por_hora = models.DecimalField(
        "Precio por hora",
        max_digits=9,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Dejar en blanco o 0 para recursos gratuitos (ej. salón de eventos).",
    )

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Recurso"
        verbose_name_plural = "Recursos"

    def __str__(self):
        return self.nombre

    def requiere_pago(self) -> bool:
        """
        Devuelve True si este recurso tiene un precio definido y mayor a 0.
        Se usa para decidir si una reserva debe generar una deuda en Pagos.
        """
        return bool(self.precio_por_hora and self.precio_por_hora > 0)


class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        APPROVED = "APPROVED", "Aprobada"
        REJECTED = "REJECTED", "Rechazada"
        CANCELLED = "CANCELLED", "Cancelada"

    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name="reservas"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservas_solicitadas",
    )

    title = models.CharField("Título/uso", max_length=200)
    notes = models.TextField("Notas", blank=True)

    start_at = models.DateTimeField("Inicio")
    end_at = models.DateTimeField("Término")

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas_aprobadas",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_at"]
        indexes = [
            models.Index(fields=["resource"]),
            models.Index(fields=["status"]),
            models.Index(fields=["start_at"]),
        ]
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"

    cancel_reason = models.TextField(
        "Motivo de cancelación",
        blank=True,
        null=True,
        help_text="Motivo indicado por el vecino al cancelar la reserva.",
    )

    def __str__(self):
        return f"{self.resource} · {self.title} · {self.start_at:%Y-%m-%d %H:%M}"

    def clean(self):
        # Si falta alguno de estos datos, no validamos todavía
        if not self.start_at or not self.end_at:
            return

        if self.start_at >= self.end_at:
            raise ValidationError(
                "La fecha/hora de inicio debe ser menor que la de término."
            )

        # OJO: usamos resource_id para no disparar el descriptor .resource
        if not self.resource_id:
            return

        qs = Reservation.objects.filter(
            resource_id=self.resource_id,
            status__in=[Reservation.Status.PENDING, Reservation.Status.APPROVED],
        ).exclude(pk=self.pk)

        qs = qs.filter(start_at__lt=self.end_at, end_at__gt=self.start_at)

        if qs.exists():
            raise ValidationError("El recurso ya está reservado en ese intervalo.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


def evidence_upload_to(instance, filename):
    return f"evidencias_inscripcion/{timezone.now():%Y/%m/%d}/{filename}"


def validate_evidence(file):
    ext = (file.name.rsplit(".", 1)[-1] or "").lower()
    if ext not in ALLOWED_EXTS:
        raise ValidationError("Formato no permitido (usa PDF, JPG, JPEG o PNG).")
    if file.size and file.size > MAX_UPLOAD_BYTES:
        raise ValidationError("El archivo supera 5 MB.")


class InscriptionEvidence(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        APPROVED = "APPROVED", "Aprobada"
        REJECTED = "REJECTED", "Rechazada"

    class DesiredRole(models.TextChoices):
        NEIGHBOUR = "VECINO", "Vecino"
        DELEGATE = "DELEGADO", "Delegado"
        TREASURER = "TESORERO", "Tesorero"
        SECRETARY = "SECRETARIO", "Secretario"
        PRESIDENT = "PRESIDENTE", "Presidente"

    file = models.FileField(
        upload_to=evidence_upload_to,
        validators=[validate_evidence],
    )

    first_name = models.CharField("Nombre", max_length=100, blank=True, null=True)
    last_name = models.CharField("Apellido", max_length=100, blank=True, null=True)

    rut = models.CharField(
        "RUT",
        max_length=12,
        blank=True,
        null=True,
        help_text="Ingresa tu RUT con o sin puntos, incluyendo el dígito verificador.",
    )

    address = models.CharField(
        "Dirección",
        max_length=255,
        blank=True,
        null=True,
    )

    email = models.EmailField(
        "Correo de contacto",
        max_length=254,
        blank=True,
        null=True,
        help_text=(
            "Usaremos este correo para avisarte si tu inscripción "
            "fue aprobada o rechazada."
        ),
    )

    desired_role = models.CharField(
        "Rol solicitado",
        max_length=20,
        choices=DesiredRole.choices,
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="insc_submissions",
    )

    resident = models.ForeignKey(
        "Resident",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="insc_validations",
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---------- Helpers ----------

    @property
    def full_name(self) -> str:
        fn = self.first_name or ""
        ln = self.last_name or ""
        return (fn + " " + ln).strip() or "Solicitante sin nombre"

    def _generate_username(self) -> str:
        """
        Genera username tipo nombre.apellido, todo en minúsculas.
        Si ya existe, agrega un sufijo 2, 3, etc.
        """
        # Normalizamos nombre y apellido por separado
        first = slugify(self.first_name or "vecino").replace("-", "")
        last = slugify(self.last_name or "").replace("-", "")

        if last:
            base = f"{first}.{last}"
        else:
            base = first

        username = base
        i = 2
        while User.objects.filter(username=username).exists():
            username = f"{base}{i}"
            i += 1
        return username

    def _generate_password(self) -> str:
        """
        Contraseña simple basada en el nombre + números aleatorios.
        (Equivale a lo que ya teníamos, pero explícito aquí).
        """
        import secrets
        base = (self.first_name or "vecino").split()[0]
        base = slugify(base) or "vecino"
        suffix = secrets.randbelow(9000) + 1000  # 4 dígitos
        return f"{base.capitalize()}{suffix}!"

    def _create_user_and_resident(self, role_code: str | None):
        """
        Crea el User + Resident y los asocia a esta inscripción.
        Devuelve (user, password_generada).

        role_code viene del formulario de gestión y suele ser:
        'Vecino', 'Delegado', 'Tesorero', 'Secretario' o 'Presidente'.
        """
        username = self._generate_username()
        password = self._generate_password()

        user = User.objects.create_user(
            username=username,
            email=self.email or "",
            first_name=self.first_name or "",
            last_name=self.last_name or "",
            password=password,
        )

        # Mapear el valor del select a un grupo de Django
        role_to_group = {
            "Vecino": "Vecino",
            "Delegado": "Delegado",
            "Tesorero": "Tesorero",
            "Secretario": "Secretario",
            "Presidente": "Presidente",
        }
        group_name = role_to_group.get(role_code)

        if group_name:
            try:
                group = Group.objects.get(name=group_name)
                user.groups.add(group)
            except Group.DoesNotExist:
                # Si falta el grupo, simplemente no lo asignamos
                pass

        # (Opcional) también guardamos el rol interno DesiredRole,
        # por si quieres usarlo más adelante.
        desired_map = {
            "Vecino": self.DesiredRole.NEIGHBOUR,
            "Delegado": self.DesiredRole.DELEGATE,
            "Tesorero": self.DesiredRole.TREASURER,
            "Secretario": self.DesiredRole.SECRETARY,
            "Presidente": self.DesiredRole.PRESIDENT,
        }
        if role_code in desired_map:
            self.desired_role = desired_map[role_code]

        # Crear Resident enlazado al User
        resident = Resident.objects.create(
            nombre=self.full_name,
            email=self.email or "",
            direccion=self.address or "",
            activo=True,
            user=user,
            rut=self.rut or None,
        )

        self.resident = resident
        self.save(update_fields=["resident", "desired_role"])

        return user, password


    # ---------- Lógica de aprobación / rechazo ----------

    def approve(self, user, note: str = "", role_code: str | None = None):
        """
        Marca la inscripción como APROBADA, crea usuario/residente si hace falta
        y envía un correo al vecino con sus credenciales.
        """
        self.status = self.Status.APPROVED
        self.validated_by = user
        self.validated_at = timezone.now()
        self.note = note

        # Crear user + resident sólo si aún no se han creado
        created_user = None
        password = None
        if not self.resident:
            created_user, password = self._create_user_and_resident(role_code)
        self.save()

        # Enviar correo
        if self.email:
            try:
                # Rol para mostrar en el correo
                if role_code:
                    role_label = role_code
                elif self.desired_role:
                    role_label = self.get_desired_role_display()
                else:
                    role_label = "Vecino"

                cuerpo = (
                    f"Hola {self.full_name},\n\n"
                    "Tu solicitud para unirte a la Junta de Vecinos UT ha sido APROBADA.\n\n"
                )

                if created_user and password:
                    cuerpo += (
                        "Puedes acceder a la plataforma con estas credenciales:\n"
                        f" - Usuario: {created_user.username}\n"
                        f" - Contraseña: {password}\n"
                        f" - Rol asignado: {role_label}\n\n"
                        "Te recomendamos cambiar la contraseña después del primer ingreso.\n\n"
                    )
                else:
                    cuerpo += (
                        "Tus datos han sido vinculados a un usuario existente de la plataforma.\n\n"
                    )

                if note:
                    cuerpo += f"Nota del equipo: {note}\n\n"

                cuerpo += "Saludos,\nJunta de Vecinos UT\n"

                email = EmailMessage(
                    subject="Inscripción aprobada – Junta de Vecinos UT",
                    body=cuerpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[self.email],
                )
                email.send(fail_silently=False)
            except Exception as e:
                print("ERROR enviando correo de inscripción aprobada:", e)


    def reject(self, user, note: str = ""):
        """
        Marca la inscripción como RECHAZADA y envía un correo con el motivo.
        """
        self.status = self.Status.REJECTED
        self.validated_by = user
        self.validated_at = timezone.now()
        self.note = note
        self.save()

        if self.email:
            try:
                cuerpo = (
                    f"Hola {self.full_name},\n\n"
                    "Lamentamos informar que tu solicitud para unirte a la Junta de "
                    "Vecinos UT ha sido RECHAZADA, ya que el archivo enviado o alguno "
                    "de los datos proporcionados no son correctos.\n\n"
                    f"Motivo: {note or 'Sin comentarios adicionales.'}\n\n"
                    "Puedes corregir la información y volver a enviar tu solicitud "
                    "cuando quieras.\n\n"
                    "Saludos,\nJunta de Vecinos UT\n"
                )
                email = EmailMessage(
                    subject="Inscripción rechazada – Junta de Vecinos UT",
                    body=cuerpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[self.email],
                )
                email.send(fail_silently=False)
            except Exception as e:
                print("ERROR enviando correo de inscripción rechazada:", e)

    def __str__(self):
        return f"Inscripción #{self.pk} - {self.get_status_display()} - {self.full_name}"

class Notification(models.Model):
    TYPE_ANNOUNCEMENT = "announcement"
    TYPE_INCIDENT = "incident"

    TYPE_CHOICES = [
        (TYPE_ANNOUNCEMENT, "Aviso"),
        (TYPE_INCIDENT, "Incidencia"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.TextField()
    url = models.CharField(
        max_length=255,
        blank=True,
        help_text="URL a donde llevamos al usuario al hacer clic en la notificación",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]




