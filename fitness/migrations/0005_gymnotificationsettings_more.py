from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fitness', '0004_gymnotification'),
    ]

    operations = [
        migrations.AddField(model_name='gymnotificationsettings', name='new_membership_created', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='gymnotificationsettings', name='membership_renewed', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='gymnotificationsettings', name='partial_payment', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='gymnotificationsettings', name='member_updated', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='gymnotificationsettings', name='member_deactivated', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='gymnotificationsettings', name='member_check_in', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='gymnotificationsettings', name='new_staff_user_created', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='gymnotificationsettings', name='user_role_changed', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='gymnotificationsettings', name='user_deactivated', field=models.BooleanField(default=True)),
    ]
