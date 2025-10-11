from django.db import models
from django.contrib.auth import get_user_model

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
