from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fitness', '0012_classschedule'),
    ]

    operations = [
        migrations.AddField(
            model_name='classschedule',
            name='group',
            field=models.CharField(
                blank=True,
                choices=[('', 'All ages'), ('kids', 'Kids'), ('adults', 'Adults')],
                default='',
                help_text='Optional kids or adults label for this weekly slot.',
                max_length=20,
            ),
        ),
    ]
