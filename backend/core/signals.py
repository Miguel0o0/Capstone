from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import Announcement, Incident, Notification

User = get_user_model()


@receiver(post_save, sender=Announcement)
def notify_new_announcement(sender, instance, created, **kwargs):
    """
    Cuando se crea un nuevo aviso, notificamos a todos los usuarios activos
    EXCEPTO al autor que lo creó.
    """
    if not created:
        return

    author = getattr(instance, "author", None)  # o "created_by" si ese es el campo
    author_id = author.id if author else None

    # De momento: todos los usuarios activos menos el autor
    recipients = User.objects.filter(is_active=True)
    if author_id:
        recipients = recipients.exclude(id=author_id)

    url = reverse("core:announcement_list")

    notifications = []
    for user in recipients:
        notifications.append(
            Notification(
                user=user,
                type=Notification.TYPE_ANNOUNCEMENT,
                message="Se ha publicado un nuevo aviso en la Junta.",
                url=url,
                is_read=False,
            )
        )

    if notifications:
        Notification.objects.bulk_create(notifications)


@receiver(post_save, sender=Incident)
def notify_new_incident(sender, instance, created, **kwargs):
    """
    Cuando se crea una nueva incidencia, notificamos a la directiva
    (Presidente, Delegado, Secretario, Tesorero, Admin) EXCEPTO al usuario
    que reportó la incidencia.
    """
    if not created:
        return

    reporter = getattr(instance, "created_by", None)  # este campo ya comprobamos que existe
    reporter_id = reporter.id if reporter else None

    board_groups = ["Presidente", "Delegado", "Secretario", "Tesorero", "Admin"]

    recipients = (
        User.objects
        .filter(is_active=True, groups__name__in=board_groups)
        .distinct()
    )
    if reporter_id:
        recipients = recipients.exclude(id=reporter_id)

    url = reverse("core:incident_mine")

    notifications = []
    for user in recipients:
        notifications.append(
            Notification(
                user=user,
                type=Notification.TYPE_INCIDENT,
                message="Se ha registrado una nueva incidencia en la Junta.",
                url=url,
                is_read=False,
            )
        )

    if notifications:
        Notification.objects.bulk_create(notifications)
