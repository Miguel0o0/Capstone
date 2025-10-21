from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q

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
    # ← añade este campo
    period = models.CharField(
        "Periodo (YYYY-MM)",
        max_length=7,
        unique=True,
        help_text="Ej: 2025-10",
    )

    amount = models.DecimalField("Monto", max_digits=9, decimal_places=2)

    class Meta:
        ordering = ["-period"]  # ahora sí existe

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
