from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0008_alter_reservation_email_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="phone",
            field=models.CharField(default="", max_length=40, verbose_name="신청자 전화번호"),
        ),
    ]
