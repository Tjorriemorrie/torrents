# Generated by Django 4.0.6 on 2024-04-02 07:37

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('main', '0007_torrent_status_at_alter_title_earliest_upload_at_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='torrent',
            name='status_at',
        ),
        migrations.AddField(
            model_name='title',
            name='status_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
