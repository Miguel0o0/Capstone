from django.urls import NoReverseMatch, reverse


def nav_items(request):
    u = request.user
    items = []
    if not u.is_authenticated:
        return {"nav_items": items}

    def rev_any(candidates: list[str]) -> str | None:
        for name in candidates:
            try:
                return reverse(name)
            except NoReverseMatch:
                continue
        return None

    def add(label: str, urlnames: list[str], perm: str | None = None):
        if perm and not u.has_perm(perm):
            return
        url = rev_any(urlnames)
        if url:
            items.append({"label": label, "url": url})

    # Público / Vecino
    add(
        "Avisos",
        ["core:announcement_list", "core:announcements"],
        "core.view_announcement",
    )
    add("Reuniones", ["core:meeting_list", "core:meetings"], "core.view_meeting")
    add("Mis pagos", ["core:my_payments"], "core.view_payment")
    add(
        "Documentos",
        ["core:documents_list", "core:documents", "core:document_list"],
        "core.view_document",
    )
    add(
        "Incidencias",
        ["core:incident_mine", "core:incidents_mine"],
        "core.add_incident",
    )
    add(
        "Reservas",
        ["core:reservation_mine", "core:reservations_mine"],
        "core.view_reservation",
    )

    # --- Solo gestión por GRUPO, no por permisos ---
    management_groups = {"Admin", "Secretario", "Presidente", "Tesorero", "Delegado"}
    is_management = (
        u.groups.filter(name__in=management_groups).exists() or u.is_superuser
    )

    if is_management:
        add("Incidencias (admin)", ["core:incident_admin"])
        add("Reservas (admin)", ["core:reservation_admin"])
        add("Cuotas", ["core:fee_list", "core:fees"])
        add("Pagos (admin)", ["core:payment_list_admin"])
        add("Subir documento", ["core:documents-create", "core:document_create"])
        add("Inscripciones", ["core:insc_admin"])

    return {"nav_items": items}
