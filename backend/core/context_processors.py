# backend/core/context_processors.py
from django.urls import reverse


def nav_items(request):
    u = request.user
    items = []
    if not u.is_authenticated:
        return {"nav_items": items}

    # ---- Roles
    is_admin_or_secretary = (
        u.is_superuser or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
    )
    is_president = u.groups.filter(name="Presidente").exists()
    is_delegate = u.groups.filter(name="Delegado").exists()
    is_treasurer = u.groups.filter(name="Tesorero").exists()

    # Mesa directiva "general" (panel, incidencias admin, reservas admin, etc.)
    is_management_general = is_admin_or_secretary or is_president
    # Gestión de pagos (Admin, Secretario, Presidente y Tesorero)
    is_payments_management = is_admin_or_secretary or is_president or is_treasurer

    # ---- Comunes
    items.append({"label": "Avisos", "url": reverse("core:announcement_list")})
    # OJO: solo roles de gestión ven Reuniones, el vecino NO
    if not u.groups.filter(name="Vecino").exists():
        items.append({"label": "Reuniones", "url": reverse("core:meeting_list")})

    # ---- Pagos
    # 1) Tesorero: "Gestión de pagos" → vista admin con todos los pagos
    if is_treasurer and u.has_perm("core.view_payment"):
        items.append(
            {
                "label": "Gestión de pagos",
                "url": reverse("core:payment_list_admin"),
            }
        )

    # 2) Delegado: "Pagos" → misma vista admin, pero modo solo lectura
    elif is_delegate and u.has_perm("core.view_payment"):
        items.append(
            {
                "label": "Pagos",
                "url": reverse("core:payment_list_admin"),
            }
        )

    # 3) Resto (vecinos y otros perfiles que pagan como vecinos): "Mis pagos"
    else:
        items.append(
            {
                "label": "Mis pagos",
                "url": reverse("core:my_payments"),
            }
        )

    # Resto de secciones comunes
    items.append({"label": "Incidencias", "url": reverse("core:incident_mine")})
    items.append({"label": "Reservas", "url": reverse("core:reservation_mine")})
    items.append({"label": "Documentos", "url": reverse("core:documents-list")})

    # ---- Gestión general (solo Admin/Secretario/Presidente, NO Delegado/Tesorero)
    if is_management_general and not is_delegate:
        items.append({"label": "Panel", "url": reverse("core:dashboard")})

        # Cuotas: mesa directiva y Tesorero
        if is_payments_management and u.has_perm("core.view_fee"):
            items.append({"label": "Cuotas", "url": reverse("core:fee_list")})

        # Pagos admin (listado completo)
        if is_payments_management and (
            u.has_perm("core.view_payment") or u.has_perm("core.change_payment")
        ):
            items.append(
                {"label": "Pagos (admin)", "url": reverse("core:payment_list_admin")}
            )

        if u.has_perm("core.view_incident") or u.has_perm("core.change_incident"):
            items.append(
                {"label": "Incidencias (admin)", "url": reverse("core:incident_admin")}
            )

        if u.has_perm("core.view_reservation") or u.has_perm("core.change_reservation"):
            items.append(
                {"label": "Reservas (admin)", "url": reverse("core:reservation_admin")}
            )

        if u.has_perm("core.add_document"):
            items.append(
                {"label": "Subir documento", "url": reverse("core:documents-create")}
            )

    # ---- Presidencia (ver vecinos)
    if (u.is_superuser or is_president) and u.has_perm("core.view_resident"):
        items.append(
            {"label": "Presidencia", "url": reverse("core:president_residents")}
        )

    # ---- Filtro defensivo final: nunca mostrar ítems 'admin' a no-management general
    if not is_management_general:
        items = [it for it in items if "admin" not in it["label"].lower()]

    return {"nav_items": items}
