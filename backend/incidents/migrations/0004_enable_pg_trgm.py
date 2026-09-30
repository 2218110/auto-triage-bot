from django.db import migrations


class Migration(migrations.Migration):
    
    dependencies = [
        ("incidents", "0003_ticket_remove_knowledgerecord_resolution"),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
        ),
    ]