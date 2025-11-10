from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ObjectDoesNotExist


class Command(BaseCommand):
    help = "Crea o actualiza grupos y permisos según los roles definidos"

    def handle(self, *args, **options):
        APP = "core"  # ajusta si tu app no es 'core'

        # Modelos reales definidos en tu app
        MODELS = [
            "announcement", "meeting", "minutes", "fee", "payment",
            "resident", "resource", "reservation", "incident"
        ]

        # Permisos diferenciados por rol
        perms_by_role = {
            "Presidente": "ALL",
            "Secretario": {
                "announcement": ["add", "change", "delete", "view"],
                "meeting":      ["add", "change", "delete", "view"],
                "minutes":      ["add", "change", "delete", "view"],
                "fee":          ["view"],
                "payment":      ["view"],
            },
            "Tesorero": {
                "fee":      ["add", "change", "delete", "view"],
                "payment":  ["add", "change", "delete", "view"],
                "announcement": ["view"],
                "meeting":      ["view"],
            },
            "Delegado": {
                "announcement": ["add", "change", "delete", "view"],
                "minutes":      ["add", "change", "delete", "view"],
                "meeting":      ["view"],
                "fee":          ["view"],
                "payment":      ["view"],
            },
            "Vecino": {
                "announcement": ["view"],
                "meeting":      ["view"],
                "minutes":      ["view"],
                "payment":      ["view"],
                "reservation":  ["add", "change", "view"],
                "incident":     ["add", "view"],
            },
        }

        def grant(group, model, actions):
            for a in actions:
                code = f"{a}_{model}"
                try:
                    perm = Permission.objects.get(codename=code)
                    group.permissions.add(perm)
                except ObjectDoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"[WARN] Permiso no existe: {code} — revisa app/modelo o migra."
                    ))

        for role, spec in perms_by_role.items():
            group, _ = Group.objects.get_or_create(name=role)
            if spec == "ALL":
                for m in MODELS:
                    grant(group, m, ["add", "change", "delete", "view"])
            else:
                for m, actions in spec.items():
                    grant(group, m, actions)

        self.stdout.write(self.style.SUCCESS("✅ Grupos y permisos configurados correctamente."))
