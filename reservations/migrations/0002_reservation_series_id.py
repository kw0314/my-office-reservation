from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="series_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
