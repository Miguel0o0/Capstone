from django.conf import settings
from django.urls import reverse

# Si prefieres evitar posibles imports circulares,
# puedes mover el import de Notification dentro de la
# función `notifications`, no hay problema.
from .models import Notification


def site_settings(request):
    """
    Context processor para exponer algunos ajustes globales en todas las plantillas.
    Puedes agregar más claves si las necesitas en tus templates.
    """
    return {
        "DEBUG": settings.DEBUG,
        "SITE_NAME": "Junta UT",
    }


def nav_items(request):
    u = request.user
    items = []

    # Usuarios anónimos: sin menú; base.html muestra "Quiero unirme" + "Iniciar sesión"
    if not u.is_authenticated:
        return {"nav_items": items}

    # ---- Roles
    is_admin = u.groups.filter(name="Admin").exists()
    is_secretary = u.groups.filter(name="Secretario").exists()
    is_president = u.groups.filter(name="Presidente").exists()
    is_delegate = u.groups.filter(name="Delegado").exists()
    is_treasurer = u.groups.filter(name="Tesorero").exists()
    is_vecino = u.groups.filter(name="Vecino").exists()

    # Mesa directiva "general"
    is_admin_or_secretary = u.is_superuser or is_admin or is_secretary
    is_management_general = is_admin_or_secretary or is_president

    # ---- Comunes
    items.append({"label": "Avisos", "url": reverse("core:announcement_list")})

    # Reuniones: todos menos el vecino
    if not is_vecino:
        items.append({"label": "Reuniones", "url": reverse("core:meeting_list")})

    # ---- Pagos
    # Vecino: solo ve "Mis pagos"
    if is_vecino:
        items.append(
            {
                "label": "Mis pagos",
                "url": reverse("core:my_payments"),
            }
        )
    else:
        # Resto de roles (Admin, Secretario, Presidente, Delegado, Tesorero)
        items.append(
            {
                "label": "Pagos",
                "url": reverse("core:payment_list_admin"),
            }
        )

    # ---- Resto de secciones comunes
    items.append({"label": "Incidencias", "url": reverse("core:incident_mine")})
    items.append({"label": "Reservas", "url": reverse("core:reservation_mine")})
    items.append({"label": "Documentos", "url": reverse("core:documents-list")})

    # ---- Inscripciones
    # SOLO Admin / Secretario / Presidente / superuser ven el panel de inscripciones.
    # Los vecinos / delegado / tesorero NO ven este ítem.
    if u.is_superuser or is_admin or is_secretary or is_president:
        if u.has_perm("core.view_inscriptionevidence"):
            items.append({"label": "Inscripciones", "url": reverse("core:insc_admin")})

    # ---- Gestión general (Admin / Secretario / Presidente, pero NO Delegado)
    if is_management_general and not is_delegate:
        # Equipo de gestión SOLO Admin / Presidente / superuser (no Secretario)
        if u.is_superuser or is_admin or is_president:
            items.append(
                {
                    "label": "Equipo de gestión",
                    "url": reverse("core:dashboard"),
                }
            )

        # "Subir documento" SOLO Presidente (y superuser)
        if (u.is_superuser or is_president) and u.has_perm("core.add_document"):
            items.append(
                {"label": "Subir documento", "url": reverse("core:documents-create")}
            )

    # ---- Presidencia (gestión de vecinos)
    if (u.is_superuser or is_president) and u.has_perm("core.view_resident"):
        items.append(
            {"label": "Presidencia", "url": reverse("core:president_residents")}
        )

    return {"nav_items": items}

def notifications(request):
    """
    Contexto base para la campana de notificaciones.
    Ahora diferenciamos entre avisos e incidencias.
    """
    if not request.user.is_authenticated:
        return {
            "notifications_unread_count": 0,
            "notifications_recent": [],
        }

    from .models import Notification  # import local para evitar ciclos

    # Todos los no leídos (para el número rojo de la campana)
    base_qs = (
        Notification.objects
        .filter(user=request.user, is_read=False)
        .order_by("-created_at")
    )

    unread_count = base_qs.count()

    # Solo mostramos los 5 más recientes en el dropdown
    recent_qs = list(base_qs[:5])

    notifications_recent = []

    for n in recent_qs:
        # --- Título y resumen según el tipo de notificación ---

        # Heurística extra por si type viene vacío: miramos la URL
        is_announcement = (
            n.type == Notification.TYPE_ANNOUNCEMENT
            or (not n.type and (n.url or "").startswith("/avisos"))
        )
        is_incident = (
            n.type == Notification.TYPE_INCIDENT
            or (not n.type and (n.url or "").startswith("/incidencias"))
        )

        if is_announcement:
            title = "Se ha publicado un nuevo aviso"
            summary = "Revisa los avisos para estar al día con la junta."
        elif is_incident:
            title = "Se ha registrado una nueva incidencia"
            summary = "Revisa las incidencias para estar al tanto de todo."
        else:
            # Fallback genérico (para notificaciones antiguas u otros tipos)
            title = "Notificación"
            summary = n.message or ""

        notifications_recent.append(
            {
                "title": title,
                "summary": summary,
                "url": n.url or "#",
            }
        )

    return {
        "notifications_unread_count": unread_count,
        "notifications_recent": notifications_recent,
    }

