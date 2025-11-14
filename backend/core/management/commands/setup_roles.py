from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea o actualiza grupos y permisos según los roles definidos"

    def handle(self, *args, **options):
        APP = "core"  # ajusta si tu app no es 'core'

        # Modelos (ContentType.model en minúsculas)
        # Ajusta nombres si tu modelo real difiere (p.ej. 'document' vs 'documento')
        MODELS = [
            "announcement",
            "meeting",
            "minutes",
            "fee",
            "payment",
            "resident",
            "reservation",
            "incident",
            "document",  # <-- añade si tu modelo existe (Document)
            "inscriptionevidence",  # <-- nuevo feature
        ]

        # Helpers -------------------------
        def ct(model):
            return ContentType.objects.get(app_label=APP, model=model)

        def perms_for(model, actions):
            """Devuelve objetos Permission para el model dado (filtrando por content_type)."""
            ctype = ct(model)
            out = []
            for a in actions:
                code = f"{a}_{model}"
                try:
                    out.append(
                        Permission.objects.get(codename=code, content_type=ctype)
                    )
                except Permission.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"[WARN] Falta permiso: {APP}.{code}")
                    )
            return out

        def grant(group, model, actions):
            group.permissions.add(*perms_for(model, actions))

        def grant_many(group, models, actions):
            for m in models:
                grant(group, m, actions)

        # ----------------- MATRIZ por rol -----------------
        #
        # Leyenda: view (V), add (C), change (E), delete (B)
        #
        # Presidente:
        # - Avisos, Reuniones, Actas, Documentos, Reservas, Incidencias => V/C/E/B
        # - Cuotas, Pagos => V solo
        # - Gestión de vecinos (Resident) => V/C/E/B
        # - InscriptionEvidence => ver/cambiar (gestiona inscripción)
        #
        # Secretario:
        # - Avisos, Reuniones, Actas => V/C/E/B
        # - Cuotas, Pagos => V solo
        # - Documentos => V/C/E/B
        # - Reservas => V/C/E/B
        # - Incidencias => V/C/E/B
        # - Resident (si administra padrones desde presidencia, aquí lo dejamos solo V; ajusta si quieres C/E/B)
        # - InscriptionEvidence => ver/cambiar
        #
        # Tesorero:
        # - Cuotas, Pagos => V/C/E/B
        # - Avisos, Reuniones, Actas => V solo
        # - Documentos => V/C/E/B
        # - Reservas => V/C/E/B
        # - Incidencias => V/C/E/B
        # - InscriptionEvidence => sin acceso
        #
        # Delegado:
        # - Avisos, Actas => V/C/E/B
        # - Reuniones => V solo
        # - Cuotas, Pagos => V solo
        # - Documentos, Reservas, Incidencias => V/C/E/B
        # - InscriptionEvidence => sin acceso
        #
        # Vecino:
        # - Avisos => V
        # - Documentos => V (descargar)
        # - Cuotas => V (ver aranceles)
        # - Pagos => V (solo los suyos; se filtra en vistas)
        # - Reservas => V/C/E (sus reservas)
        # - Incidencias => V/C (reportar + ver)
        # - InscriptionEvidence => (solo formulario público; sin permisos admin)
        #
        # Admin (superuser) ya tiene todo por defecto; el grupo "Admin" lo dejamos FULL por simetría.

        # Asegurar grupos
        roles = ["Admin", "Presidente", "Secretario", "Tesorero", "Delegado", "Vecino"]
        groups = {name: Group.objects.get_or_create(name=name)[0] for name in roles}

        # Limpieza: quitamos todos los perms actuales y reasignamos según matriz
        for g in groups.values():
            g.permissions.clear()

        FULL = ["view", "add", "change", "delete"]
        VIEW_ONLY = ["view"]

        # Grupos/Matriz
        admin = groups["Admin"]
        grant_many(admin, MODELS, FULL)

        presidente = groups["Presidente"]
        grant_many(
            presidente,
            [
                "announcement",
                "meeting",
                "minutes",
                "document",
                "reservation",
                "incident",
            ],
            FULL,
        )
        grant_many(presidente, ["fee", "payment"], VIEW_ONLY)
        grant(presidente, "resident", FULL)
        grant(presidente, "inscriptionevidence", ["view", "change"])

        secretario = groups["Secretario"]
        grant_many(secretario, ["announcement", "meeting", "minutes"], FULL)
        grant_many(secretario, ["fee", "payment"], VIEW_ONLY)
        grant_many(secretario, ["document", "reservation", "incident"], FULL)
        grant(
            secretario, "resident", ["view"]
        )  # ajusta a FULL si le das gestión de padrón
        grant(secretario, "inscriptionevidence", ["view", "change"])

        tesorero = groups["Tesorero"]
        grant_many(tesorero, ["fee", "payment"], FULL)
        grant_many(tesorero, ["announcement", "meeting", "minutes"], VIEW_ONLY)
        grant_many(tesorero, ["document", "reservation", "incident"], FULL)
        # sin permisos sobre inscriptionevidence

        delegado = groups["Delegado"]
        grant_many(delegado, ["announcement", "minutes"], FULL)
        grant(delegado, "meeting", VIEW_ONLY)
        grant_many(delegado, ["fee", "payment"], VIEW_ONLY)
        grant_many(delegado, ["document", "reservation", "incident"], FULL)
        # sin permisos sobre inscriptionevidence

        vecino = groups["Vecino"]
        grant(vecino, "announcement", ["view"])
        grant(vecino, "document", ["view"])
        grant(vecino, "fee", ["view"])
        grant(vecino, "payment", ["view"])
        grant(
            vecino, "reservation", ["view", "add", "change"]
        )  # sólo sus reservas (filtrar en vistas)
        grant(vecino, "incident", ["view", "add", "change", "delete"])
        # sin permisos sobre inscriptionevidence

        self.stdout.write(
            self.style.SUCCESS("✅ Grupos y permisos configurados según la matriz.")
        )
