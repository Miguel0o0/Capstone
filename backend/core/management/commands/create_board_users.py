# backend/core/management/commands/create_board_users.py

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

User = get_user_model()

USERS = [
    # username, email, first_name, last_name, group_name
    ("william.presidente", "william.slopez@gmail.com", "willian", "lopez", "Presidente"),
    ("miguel.tesorero", "matias.cardenas@gmail.com", "Matias", "Cardenas", "Tesorero"),
    ("lucas.delegado", "lucas.saez@gmail.com", "Lucas", "Saez", "Delegado"),
    ("matias.secretario", "miguel.medina@gmail.com", "Miguel", "Medina", "Secretario"),
    ("daniel.vecino", "daniel.enrique@gmail.com", "Daniel", "Enrique", "Vecino"),
]

DEFAULT_PASSWORD = "Demo1234!"  # cambia luego en admin si quieres


class Command(BaseCommand):
    help = (
        "Crea usuarios demo para Presidente/Tesorero/Delegado/Secretario/Vecino "
        "y los asigna a sus grupos. Además asigna todos los permisos de 'core' "
        "al grupo Presidente."
    )

    def handle(self, *args, **options):
        created = 0
        for username, email, first, last, group_name in USERS:
            user, was_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": first,
                    "last_name": last,
                    "is_active": True,
                },
            )
            if was_created:
                user.set_password(DEFAULT_PASSWORD)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✔ Usuario creado: {username} / {DEFAULT_PASSWORD}"
                    )
                )
                created += 1
            else:
                self.stdout.write(f"= Usuario ya existía: {username}")

            try:
                group = Group.objects.get(name=group_name)
            except Group.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"[WARN] No existe el grupo '{group_name}'. Ejecuta setup_roles."
                    )
                )
                continue

            user.groups.add(group)
            user.save()
            self.stdout.write(f"→ Asignado a grupo: {group_name}")

        self.stdout.write(self.style.SUCCESS(f"Listo. Usuarios nuevos: {created}"))
        self.stdout.write(
            "Recuerda: presidente/secretario ven 'Inscripciones'; tesorero/delegado no."
        )

        # ------------------------------------------------------------------
        # Asignar TODOS los permisos del app 'core' al grupo Presidente
        # ------------------------------------------------------------------
        try:
            presidente_group = Group.objects.get(name="Presidente")
        except Group.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    "[WARN] No existe el grupo 'Presidente'. "
                    "Ejecuta setup_roles para crearlo y luego vuelve a correr este comando."
                )
            )
        else:
            core_perms = Permission.objects.filter(content_type__app_label="core")
            presidente_group.permissions.set(core_perms)
            self.stdout.write(
                self.style.SUCCESS(
                    "✔ Permisos del app 'core' asignados al grupo Presidente."
                )
            )
