# backend/core/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import (
    Announcement,
    Incident,
    Notification,
    Meeting,
    Payment,
    InscriptionEvidence,
)

User = get_user_model()


def get_related_user(instance, field_names):
    """
    Intenta obtener un usuario asociado a la instancia usando
    varios posibles nombres de campo.
    """
    for name in field_names:
        val = getattr(instance, name, None)
        if isinstance(val, User):
            return val
    return None


# --------------------------
# Avisos
# --------------------------
@receiver(post_save, sender=Announcement)
def notify_new_announcement(sender, instance, created, **kwargs):
    """
    Cuando se crea un nuevo aviso, notificamos a todos los usuarios activos
    EXCEPTO al autor que lo creó.
    """
    if not created:
        return

    author = get_related_user(instance, ["creado_por", "author", "created_by", "user"])

    recipients = User.objects.filter(is_active=True)
    if author:
        recipients = recipients.exclude(id=author.id)

    url = reverse("core:announcement_list")

    notifications = [
        Notification(
            user=user,
            type=Notification.TYPE_ANNOUNCEMENT,
            message="Se ha publicado un nuevo aviso en la Junta.",
            url=url,
            is_read=False,
        )
        for user in recipients
    ]

    if notifications:
        Notification.objects.bulk_create(notifications)


# --------------------------
# Incidencias
# --------------------------
@receiver(post_save, sender=Incident)
def notify_new_incident(sender, instance, created, **kwargs):
    """
    Cuando se crea una nueva incidencia, notificamos a la directiva
    EXCEPTO al usuario que la reportó.
    """
    if not created:
        return

    reporter = get_related_user(
        instance,
        ["reportado_por", "created_by", "author", "user"],
    )

    board_groups = ["Presidente", "Delegado", "Secretario", "Tesorero", "Admin"]

    recipients = (
        User.objects.filter(is_active=True, groups__name__in=board_groups).distinct()
    )
    if reporter:
        recipients = recipients.exclude(id=reporter.id)

    url = reverse("core:incident_mine")

    notifications = [
        Notification(
            user=user,
            type=Notification.TYPE_INCIDENT,
            message="Se ha registrado una nueva incidencia en la Junta.",
            url=url,
            is_read=False,
        )
        for user in recipients
    ]

    if notifications:
        Notification.objects.bulk_create(notifications)


# --------------------------
# Reuniones
# --------------------------
@receiver(post_save, sender=Meeting)
def notify_new_meeting(sender, instance, created, **kwargs):
    """
    Cuando se crea una nueva reunión, notificamos a la mesa/directiva.
    Si en el modelo Meeting agregaste un campo creador (creado_por/created_by),
    se excluirá al creador automáticamente.
    """
    if not created:
        return

    creator = get_related_user(instance, ["created_by", "creado_por", "user"])

    board_groups = ["Presidente", "Delegado", "Secretario", "Tesorero", "Admin"]

    recipients = (
        User.objects.filter(is_active=True, groups__name__in=board_groups).distinct()
    )
    if creator:
        recipients = recipients.exclude(id=creator.id)

    url = reverse("core:meeting_list")

    notifications = [
        Notification(
            user=user,
            type=Notification.TYPE_MEETING,
            message="Se ha programado una nueva reunión de la Junta.",
            url=url,
            is_read=False,
            is_important=False,
        )
        for user in recipients
    ]

    if notifications:
        Notification.objects.bulk_create(notifications)


# ==========================================================
# Pagos: detectar cambios de estado (aprobado / rechazado)
# ==========================================================

@receiver(pre_save, sender=Payment)
def store_old_payment_status(sender, instance, **kwargs):
    """
    Guarda en instance._old_status el estado anterior antes de guardar.
    Así en post_save podemos saber si el estado cambió.
    """
    if not instance.pk:
        # Objeto nuevo: no hay estado anterior
        instance._old_status = None
        return

    try:
        old = sender.objects.get(pk=instance.pk)
        instance._old_status = old.status
    except sender.DoesNotExist:
        instance._old_status = None


@receiver(post_save, sender=Payment)
def notify_new_payment_created(sender, instance, created, **kwargs):
    """
    CUANDO SE CREA UN PAYMENT NUEVO:
    Notificamos a la directiva de que hay un nuevo pago pendiente de revisión.
    (esto normalmente ocurre cuando se genera la deuda de una reserva).
    """
    if not created:
        return

    board_groups = ["Presidente", "Tesorero", "Delegado", "Secretario"]
    important_groups = {"Presidente", "Tesorero"}

    recipients = (
        User.objects.filter(is_active=True, groups__name__in=board_groups).distinct()
    )

    url = reverse("core:payment_list_admin")

    notifications = []
    for user in recipients:
        user_is_important = user.groups.filter(name__in=important_groups).exists()

        notifications.append(
            Notification(
                user=user,
                type=Notification.TYPE_PAYMENT,
                message="Hay un nuevo pago pendiente de revisión.",
                url=url,
                is_read=False,
                is_important=user_is_important,
            )
        )

    if notifications:
        Notification.objects.bulk_create(notifications)


@receiver(post_save, sender=Payment)
def notify_payment_status_change(sender, instance, created, **kwargs):
    """
    CUANDO SE ACTUALIZA UN PAYMENT (no creado), revisamos si el estado cambió.
    - Si pasa a PAID  -> notificación al vecino: pago aprobado.
    - Si pasa a CANCELLED -> notificación al vecino: pago rechazado.
    """
    if created:
        # La creación ya la maneja notify_new_payment_created
        return

    old_status = getattr(instance, "_old_status", None)
    new_status = instance.status

    # Si no hay cambio de estado, no hacemos nada
    if not old_status or old_status == new_status:
        return

    # Seguridad: por si acaso no hay residente asociado
    if not instance.resident_id:
        return

    # Pago aprobado
    if new_status == Payment.STATUS_PAID:
        Notification.objects.create(
            user=instance.resident,
            type=Notification.TYPE_PAYMENT,
            message="Tu pago fue aprobado. Ya puedes hacer otra reserva.",
            url=reverse("core:reservation_create"),
            is_read=False,
            is_important=False,
        )

    # Pago rechazado / cancelado
    elif new_status == Payment.STATUS_CANCELLED:
        Notification.objects.create(
            user=instance.resident,
            type=Notification.TYPE_PAYMENT,
            message="Tu pago fue rechazado. Intenta nuevamente subiendo un nuevo comprobante.",
            url=reverse("core:my_payments"),
            is_read=False,
            is_important=False,
        )


# --------------------------
# Inscripciones
# --------------------------
@receiver(post_save, sender=InscriptionEvidence)
def notify_new_subscription(sender, instance, created, **kwargs):
    """
    Cuando se recibe una nueva solicitud de inscripción desde el formulario público,
    notificamos a Presidente y Secretario (y opcionalmente Admin) como IMPORTANTE.
    """
    if not created:
        return

    subscription_groups = ["Presidente", "Secretario", "Admin"]

    recipients = (
        User.objects.filter(is_active=True, groups__name__in=subscription_groups)
        .distinct()
    )

    url = reverse("core:insc_admin")

    notifications = [
        Notification(
            user=user,
            type=Notification.TYPE_SUBSCRIPTION,
            message="Hay una nueva solicitud de inscripción pendiente de revisión.",
            url=url,
            is_read=False,
            is_important=True,
        )
        for user in recipients
    ]

    if notifications:
        Notification.objects.bulk_create(notifications)
