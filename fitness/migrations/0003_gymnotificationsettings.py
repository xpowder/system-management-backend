from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fitness', '0002_membershipplan_trainer_attendance_membership_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='GymNotificationSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('membership_expiring_soon', models.BooleanField(default=True)),
                ('membership_expired', models.BooleanField(default=True)),
                ('outstanding_payment', models.BooleanField(default=True)),
                ('new_member_registered', models.BooleanField(default=True)),
                ('payment_received', models.BooleanField(default=True)),
                ('important_system_alerts', models.BooleanField(default=True)),
            ],
        ),
    ]
