from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

CANONICAL = {
    "admin": "Admin",
    "presidente": "Presidente",
    "secretario": "Secretario",
    "tesorero": "Tesorero",
    "delegado": "Delegado",
    "vecino": "Vecino",
}


class Command(BaseCommand):
    help = "Normaliza grupos: fusiona duplicados por nombre (case-insensitive) hacia nombres canónicos."

    def handle(self, *args, **opts):
        # 1) Asegurar que existan los grupos canónicos
        canon_groups = {}
        for key, canon in CANONICAL.items():
            g, _ = Group.objects.get_or_create(name=canon)
            canon_groups[key] = g

        # 2) Recorrer todos los grupos y fusionar cuando no coincidan con el canónico
        all_groups = Group.objects.all()
        merged_count = 0

        for g in all_groups:
            key = g.name.strip().lower()
            if key in CANONICAL:
                canon_name = CANONICAL[key]
                canon_group = canon_groups[key]

                if g.id == canon_group.id:
                    # Ya es el canónico, nada que hacer
                    continue

                # Fusionar permisos al canónico
                perms = Permission.objects.filter(group=g)
                canon_group.permissions.add(*perms)

                # Mover usuarios al canónico
                for u in g.user_set.all():
                    u.groups.add(canon_group)
                    u.groups.remove(g)

                # Borrar el duplicado
                g.delete()
                merged_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✔ Fusionado y eliminado grupo duplicado '{g.name}' → '{canon_name}'"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(f"Listo. Grupos fusionados: {merged_count}")
        )
        self.stdout.write("Ahora ejecuta: python manage.py setup_roles")
