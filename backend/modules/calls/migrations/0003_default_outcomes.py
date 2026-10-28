from django.db import migrations

OUTCOMES = [("Sale", "#10b981"), ("Support", "#3758f9"), ("Complaint", "#ef4444"), ("Follow-up", "#f59e0b"), ("Wrong number", "#6b7280")]


def create(apps, schema_editor):
    CallOutcome = apps.get_model("calls", "CallOutcome")
    for order, (name, colour) in enumerate(OUTCOMES):
        CallOutcome.objects.get_or_create(name=name, defaults={"colour": colour, "order": order * 10})


class Migration(migrations.Migration):
    dependencies = [("calls", "0002_initial")]

    operations = [migrations.RunPython(create, migrations.RunPython.noop)]
