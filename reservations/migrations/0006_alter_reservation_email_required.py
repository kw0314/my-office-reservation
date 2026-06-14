# Generated migration: Make email field required

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0005_reservation_email'),
    ]

    operations = [
        # Set default value for existing records without email
        migrations.RunPython(
            lambda apps, schema_editor: (
                apps.get_model('reservations', 'Reservation')
                .objects.filter(email__isnull=True)
                .update(email='no-reply@example.com')
            ),
        ),
        # Make field required
        migrations.AlterField(
            model_name='reservation',
            name='email',
            field=models.EmailField(
                blank=False,
                max_length=254,
                null=False,
                verbose_name='신청자 이메일',
            ),
        ),
    ]
