from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fitness', '0003_gymnotificationsettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='GymNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.CharField(choices=[('memberships', 'Memberships'), ('payments', 'Payments'), ('members', 'Members'), ('system', 'System')], max_length=30)),
                ('title', models.CharField(max_length=180)),
                ('message', models.TextField()),
                ('is_read', models.BooleanField(default=False)),
                ('member_id', models.PositiveIntegerField(blank=True, null=True)),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gym_notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
