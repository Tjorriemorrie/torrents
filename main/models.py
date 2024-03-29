from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Min, Max
from django.utils.timezone import now

from main.constants import CATEGORY_MOVIES, CATEGORY_TV_SHOWS, CATEGORY_GAMES, SITE_1337X, SUBCATEGORY_PCGAMES, \
    SUBCATEGORY_H264, SUBCATEGORY_BOLLYWOOD, STATUS_NEW, STATUS_SKIPPED, STATUS_FINISHED, SITE_RARBG, SUBCATEGORY_HD_TV, \
    SUBCATEGORY_SD_TV, SUBCATEGORY_DIVX_TV, SUBCATEGORY_HEVC_TV


class Timestamp(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Title(Timestamp):
    STATUS_CHOICES = (
        (STATUS_NEW, 'New'),
        (STATUS_SKIPPED, 'Skipped'),
        (STATUS_FINISHED, 'Finished'),
    )
    text = models.CharField(max_length=250, primary_key=True)
    status = models.IntegerField(choices=STATUS_CHOICES, default=STATUS_NEW)
    year = models.IntegerField(validators=(
        MinValueValidator(1990), MaxValueValidator(2030)), null=True, blank=True)
    # tv
    series = models.CharField(max_length=250, null=True, blank=True)
    season = models.IntegerField(null=True, blank=True)
    episode = models.IntegerField(null=True, blank=True)
    # stats
    earliest_upload_at = models.DateTimeField(null=True, blank=True)
    latest_upload_at = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ('text',)

    def __str__(self):
        return f'{self.text}'

    def update_stats(self):
        self.earliest_upload_at = self.torrents.aggregate(Min('uploaded_at'))['uploaded_at__min']
        self.latest_upload_at = self.torrents.aggregate(Max('uploaded_at'))['uploaded_at__max']
        if not self.earliest_upload_at or not self.latest_upload_at:
            raise ValueError()
        days_earliest = (now() - self.earliest_upload_at).days
        days_latest = (now() - self.latest_upload_at).days
        self.priority = days_earliest + days_latest

    # def save(
    #     self, force_insert=False, force_update=False, using=None, update_fields=None
    # ):
    #     if not self.priority:
    #         self.update_stats()
    #     return super().save(force_insert, force_update, using, update_fields)


class Expansion(Timestamp):
    text = models.CharField(max_length=250, primary_key=True)

    def __str__(self):
        return f'{self.text}'


class Torrent(Timestamp):
    CATEGORIES = (
        (CATEGORY_MOVIES, CATEGORY_MOVIES),
        (CATEGORY_TV_SHOWS, CATEGORY_TV_SHOWS),
        (CATEGORY_GAMES, CATEGORY_GAMES),
    )
    SUBCATEGORIES = (
        # movies
        (SUBCATEGORY_H264, SUBCATEGORY_H264),
        (SUBCATEGORY_BOLLYWOOD, SUBCATEGORY_BOLLYWOOD),
        # tv
        (SUBCATEGORY_HD_TV, SUBCATEGORY_HD_TV),
        (SUBCATEGORY_SD_TV, SUBCATEGORY_SD_TV),
        (SUBCATEGORY_DIVX_TV, SUBCATEGORY_DIVX_TV),
        (SUBCATEGORY_HEVC_TV, SUBCATEGORY_HEVC_TV),
        # games
        (SUBCATEGORY_PCGAMES, SUBCATEGORY_PCGAMES),
    )
    SITES = (
        (SITE_1337X, SITE_1337X),
        (SITE_RARBG, SITE_RARBG),
    )
    site = models.CharField(max_length=100, choices=SITES)
    category = models.CharField(max_length=100, choices=CATEGORIES)
    subcategory = models.CharField(max_length=100, choices=SUBCATEGORIES)

    name = models.CharField(max_length=250)
    url = models.CharField(max_length=250, unique=True)
    seeders = models.IntegerField()
    leechers = models.IntegerField()
    uploaded_at = models.DateTimeField()
    size = models.IntegerField()
    uploader = models.CharField(max_length=250)

    title = models.ForeignKey(Title, on_delete=models.SET_NULL, related_name='torrents', null=True, blank=True)

    pirate = models.CharField(max_length=250, null=True, blank=True)

    # media
    video_codec = models.CharField(max_length=250, null=True, blank=True)
    audio_codec = models.CharField(max_length=250, null=True, blank=True)
    source = models.CharField(max_length=250, null=True, blank=True)
    resolution = models.CharField(max_length=250, null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    subtitle = models.CharField(max_length=50, null=True, blank=True)
    language = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self) -> str:
        return f'<{self.category} {self.name}>'

    # def save(
    #     self, force_insert=False, force_update=False, using=None, update_fields=None
    # ):
    #     self.title and self.title.update_stats()
    #     return super().save(force_insert, force_update, using, update_fields)