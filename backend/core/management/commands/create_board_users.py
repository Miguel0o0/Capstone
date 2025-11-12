from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

User = get_user_model()

USERS = [
    # username, email, first_name, last_name, group_name
    ("presidente1", "presidente1@example.com", "Presidente", "Uno", "Presidente"),
    ("tesorero1", "tesorero1@example.com", "Tesorero", "Uno", "Tesorero"),
    ("delegado1", "delegado1@example.com", "Delegado", "Uno", "Delegado"),
]

DEFAULT_PASSWORD = "Demo1234!"  # cambia luego en admin si quieres


class Command(BaseCommand):
    help = "Crea usuarios demo para Presidente/Tesorero/Delegado y los asigna a sus grupos."

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
