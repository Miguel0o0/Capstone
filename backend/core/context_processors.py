from django.urls import reverse


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
