from django.db import migrations

GROUPS = ["Admin", "Secretario", "Revisor", "Vecino"]


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in GROUPS:
        Group.objects.get_or_create(name=name)


def delete_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=GROUPS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("auth", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(create_groups, delete_groups),
    ]
