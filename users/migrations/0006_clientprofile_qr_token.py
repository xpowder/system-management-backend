import secrets

from django.db import migrations, models

import users.models


def generate_qr_token():
    return secrets.token_urlsafe(32)


def fill_qr_tokens(apps, schema_editor):
    ClientProfile = apps.get_model('users', 'ClientProfile')
    used = set()
    batch = []
    for profile in ClientProfile.objects.all().iterator():
        token = generate_qr_token()
        while token in used:
            token = generate_qr_token()
        used.add(token)
        profile.qr_token = token
        batch.append(profile)
        if len(batch) >= 500:
            ClientProfile.objects.bulk_update(batch, ['qr_token'])
            batch = []
    if batch:
        ClientProfile.objects.bulk_update(batch, ['qr_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_scale_list_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientprofile',
            name='qr_token',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.RunPython(fill_qr_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='clientprofile',
            name='qr_token',
            field=models.CharField(
                default=users.models.generate_qr_token,
                editable=False,
                help_text='Opaque token encoded in the member QR card. Not a login credential.',
                max_length=64,
                unique=True,
            ),
        ),
    ]
