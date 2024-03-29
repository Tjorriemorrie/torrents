# Generated by Django 4.0.6 on 2023-08-28 17:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0005_title_episode_title_season_title_series'),
    ]

    operations = [
        migrations.DeleteModel(
            name='TitleReady',
        ),
        migrations.CreateModel(
            name='Movies',
            fields=[
            ],
            options={
                'verbose_name': 'Movie',
                'verbose_name_plural': 'Movies',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('main.title',),
        ),
        migrations.CreateModel(
            name='PcGames',
            fields=[
            ],
            options={
                'verbose_name': 'PC Game',
                'verbose_name_plural': 'PC Games',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('main.title',),
        ),
        migrations.CreateModel(
            name='TvShows',
            fields=[
            ],
            options={
                'verbose_name': 'TV Show',
                'verbose_name_plural': 'TV Shows',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('main.title',),
        ),
        migrations.AddField(
            model_name='title',
            name='earliest_upload_at',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='title',
            name='latest_upload_at',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='title',
            name='priority',
            field=models.IntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='torrent',
            name='subcategory',
            field=models.CharField(choices=[('h.264/x264', 'h.264/x264'), ('bollywood', 'bollywood'), ('hd', 'hd'), ('sd', 'sd'), ('divx', 'divx'), ('hevc/x265', 'hevc/x265'), ('pcgames', 'pcgames')], max_length=100),
        ),
    ]
