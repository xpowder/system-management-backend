from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fitness', '0013_classschedule_group'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classschedule',
            name='group',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Optional calendar name for this weekly slot, for example boxing-kids.',
                max_length=80,
            ),
        ),
    ]
