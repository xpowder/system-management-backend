from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fitness', '0014_classschedule_group_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='classschedule',
            name='color',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Optional calendar color as #RRGGBB.',
                max_length=7,
            ),
        ),
    ]
