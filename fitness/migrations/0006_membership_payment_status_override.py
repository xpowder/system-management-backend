from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fitness', '0005_gymnotificationsettings_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='membership',
            name='payment_status_override',
            field=models.CharField(blank=True, choices=[('paid', 'Paid'), ('unpaid', 'Unpaid')], max_length=20),
        ),
    ]
