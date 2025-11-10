# backend/core/models.py
import os
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

User = get_user_model()


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

    class Meta:
        ordering = ["-creado_en"]

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
        "Periodo (YYYY-MM)",
        max_length=7,
        unique=True,
        help_text="Ej: 2025-10",
    )
    amount = models.DecimalField("Monto", max_digits=9, decimal_places=2)

    class Meta:
        ordering = ["-period"]

    def __str__(self):
        return f"Cuota {self.period} (${self.amount})"


class Payment(models.Model):
    # --- constantes y choices ---
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pendiente"),
        (STATUS_PAID, "Pagado"),
    )

    # --- campos ---
    resident = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="Vecino",
    )
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField("Monto", max_digits=9, decimal_places=2)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    paid_at = models.DateTimeField("Fecha de pago", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["resident", "fee"],
                condition=Q(status=STATUS_PAID),
                name="uniq_paid_per_resident_fee",
            )
        ]

    def __str__(self):
        return f"{self.resident} → {self.fee.period} ({self.get_status_display()})"


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
    ext = filename.split(".")[-1].lower()
    return os.path.join(
        "incidencias", f"{instance.created_at:%Y/%m}", f"{uuid.uuid4().hex}.{ext}"
    )


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
        return f"[{self.get_status_display()}] {self.titulo}"


def incident_upload_to(instance, filename):
    # usa fallback si created_at aún no existe
    ext = filename.split(".")[-1].lower()
    dt = getattr(instance, "created_at", None) or timezone.now()
    return os.path.join("incidencias", f"{dt:%Y/%m}", f"{uuid.uuid4().hex}.{ext}")


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

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Recurso"
        verbose_name_plural = "Recursos"

    def __str__(self):
        return self.nombre


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

    def __str__(self):
        return f"{self.resource} · {self.title} · {self.start_at:%Y-%m-%d %H:%M}"

    def clean(self):
        if self.start_at >= self.end_at:
            raise ValidationError(
                "La fecha/hora de inicio debe ser menor que la de término."
            )
        qs = Reservation.objects.filter(
            resource=self.resource,
            status__in=[Reservation.Status.PENDING, Reservation.Status.APPROVED],
        ).exclude(pk=self.pk)
        qs = qs.filter(start_at__lt=self.end_at, end_at__gt=self.start_at)
        if qs.exists():
            raise ValidationError("El recurso ya está reservado en ese intervalo.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
