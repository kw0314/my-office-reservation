from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0007_reservation_series_repeat_until"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reservation",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name="신청자 이메일"),
        ),
    ]
