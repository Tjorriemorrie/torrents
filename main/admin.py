import logging
from datetime import timedelta

from django.contrib import admin
from django.db.models import Count, F, Max, Min, Q, QuerySet, Sum
from django.urls import reverse
from django.utils.html import format_html
from django.utils.timezone import now

from main.constants import (
    CATEGORY_GAMES,
    CATEGORY_MOVIES,
    CATEGORY_TV_SHOWS,
    STATUS_FINISHED,
    STATUS_NEW,
    STATUS_SKIPPED,
)
from main.models import Title, Torrent
from main.parsing import parse_title

logger = logging.getLogger(__name__)


@admin.action(description='Parse title of torrent')
def parse_title_cmd(modeladmin, request, queryset):
    """Parse title command."""
    logger.info('Parsing titles of torrents...')
    torrents = set(t for t in queryset)
    for torrent in torrents:
        parse_title(torrent)


@admin.action(description='Mark as new')
def mark_as_new_cmd(modeladmin, request, queryset):
    """Mark as new command."""
    logger.info('Marking as new...')
    titles = set(t for t in queryset)
    for title in titles:
        title.status = STATUS_NEW
        title.status_at = now()
        title.save()


@admin.action(description='Mark as skipped')
def mark_as_skipped_cmd(modeladmin, request, queryset):
    """Mark as skipped command."""
    logger.info('Marking as skipped...')
    titles = set(t for t in queryset)
    for title in titles:
        title.status = STATUS_SKIPPED
        title.status_at = now()
        title.save()


@admin.action(description='Mark as finished')
def mark_as_finished_cmd(modeladmin, request, queryset):
    """Mark as finished command."""
    logger.info('Marking as finished...')
    titles = set(t for t in queryset)
    for title in titles:
        title.status = STATUS_FINISHED
        title.status_at = now()
        title.save()


@admin.action(description='Update torrent stats')
def update_stats_cmd(modeladmin, request, queryset):
    """Update stats command."""
    logger.info('Updating stats...')
    titles = set(t for t in queryset)
    for title in titles:
        title.update_stats()
        title.save()


@admin.register(Torrent)
class TorrentAdmin(admin.ModelAdmin):
    list_display = (
        'pk',
        'title',
        'category',
        'subcategory',
        'seeders',
        'leechers',
        'size',
        'uploader',
        'name',
        'site',
        'uploaded_at',
    )
    list_filter = ('category', 'subcategory')
    ordering = ['-seeders']
    actions = [parse_title_cmd]
    fields = ('title', 'name', 'category', 'subcategory')
    readonly_fields = ('name',)
    search_fields = ['name']

    change_list_template = 'main/torrent_change_list.html'

    def save_model(self, request, obj, form, change):
        """Save with status."""
        if 'title' in form.changed_data and obj.title.status == STATUS_SKIPPED:
            obj.title.status = STATUS_NEW
            obj.title.status_at = now()
            obj.title.save()
        return super().save_model(request, obj, form, change)


@admin.register(Title)
class TitleAdmin(admin.ModelAdmin):
    list_display = (
        'text',
        'status',
        'torrents',
        'year',
        'last_name',
        'first_upload',
        'last_upload',
    )
    search_fields = ('text',)
    list_filter = ('status',)

    def torrents(self, title: Title) -> str:
        """Torrents count."""
        return title.torrents.count()

    @admin.display(ordering=F('last_name').asc(nulls_last=None))
    def last_name(self, title: Title) -> str:
        """Last name field."""
        if last_torrent := title.torrents.order_by('uploaded_at').last():
            url = reverse('admin:main_torrent_changelist')
            return format_html(f'<a href="{url}?title={title.text}&o=-11">{last_torrent.name}</a>')

    @admin.display(ordering=F('last_upload').asc(nulls_last=None))
    def last_upload(self, title: Title) -> str:
        """Last upload field."""
        return f'{title.last_upload:%Y-%m-%d %H:%I}'

    @admin.display(ordering=F('first_upload').asc(nulls_last=None))
    def first_upload(self, title: Title) -> str:
        """Firts upload field."""
        return f'{title.first_upload:%Y-%m-%d %H:%I}'

    def get_queryset(self, request) -> QuerySet:
        """Get with dates."""
        qs = self.model._default_manager.get_queryset()
        # qs = qs.annotate(last_upload=ExpressionWrapper(now() -
        # F('oldest_updated_at'), models.FloatField()))
        qs = qs.annotate(first_upload=Min('torrents__uploaded_at'))
        qs = qs.annotate(last_upload=Max('torrents__uploaded_at'))
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


class PcGames(Title):
    class Meta:
        proxy = True
        verbose_name = 'PC Game'
        verbose_name_plural = 'PC Games'


@admin.register(PcGames)
class PcGamesAdmin(admin.ModelAdmin):
    list_display = (
        'text',
        'priority',
        'year',
        'torrents',
        'earliest_upload_at',
        'latest_upload_at',
        'last_name',
        'status',
    )
    ordering = (
        '-year',
        'status',
    )
    list_filter = ('status',)
    actions = [mark_as_skipped_cmd, mark_as_finished_cmd, update_stats_cmd]

    change_list_template = 'main/pcgames_change_list.html'

    def get_queryset(self, request):
        """Get with annotations."""
        qs = self.model._default_manager.get_queryset()
        qs = qs.filter(torrents__category=CATEGORY_GAMES)

        days = 30 * 24
        time_cutoff = now() - timedelta(days=days)

        # qs = qs.annotate(lastest_uploaded_at=Max('torrents__uploaded_at'))
        qs = qs.annotate(earliest_uploaded_at=Min('torrents__uploaded_at'))
        qs = qs.filter(priority__gte=days)

        qs = qs.annotate(
            num_before=Count('torrents', filter=Q(torrents__uploaded_at__lt=time_cutoff))
        )
        qs = qs.annotate(
            num_after=Count('torrents', filter=Q(torrents__uploaded_at__gt=time_cutoff))
        )

        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    # @admin.display(ordering=F('lastest_uploaded_at').asc(nulls_last=None))
    # def lastest_uploaded_at(self, title: Title) -> str:
    #     old = f'{title.lastest_uploaded_at:%Y-%m-%d %H:%I}'
    #     return f'{old}'
    #
    # @admin.display(ordering=F('earliest_upload_at').asc(nulls_last=None))
    # def earliest_uploaded_at(self, title: Title) -> str:
    #     old = f'{title.earliest_uploaded_at:%Y-%m-%d %H:%I}'
    #     return f'{old}'

    @admin.display(ordering=F('num_before').desc(nulls_last=None))
    def num_before(self, title: Title) -> str:
        """Number before field."""
        return title.num_before

    @admin.display(ordering=F('num_after').desc(nulls_last=None))
    def num_after(self, title: Title) -> str:
        """Number after field."""
        return title.num_after

    def torrents(self, title: Title) -> str:
        """Torrents count."""
        return title.torrents.count()

    def last_name(self, title: Title) -> str:
        """Last name field."""
        if last_torrent := title.torrents.order_by('uploaded_at').last():
            url = reverse('admin:main_torrent_changelist')
            clean_name = last_torrent.name.replace('{', '').replace('}', '')
            return format_html(f'<a href="{url}?title={title.text}&o=-11">{clean_name}</a>')


class TvShows(Title):
    class Meta:
        proxy = True
        verbose_name = 'TV Show'
        verbose_name_plural = 'TV Shows'


@admin.register(TvShows)
class TVShowsAdmin(admin.ModelAdmin):
    list_display = (
        'seeders',
        'earliest_uploaded_at',
        'series',
        'season',
        'episode',
        'status',
        'torrents',
        'last_name',
    )
    ordering = ('series', 'season', 'episode')
    actions = [mark_as_skipped_cmd, mark_as_finished_cmd, mark_as_new_cmd]
    # list_filter = ('status',)
    change_list_template = 'main/tvshows_change_list.html'
    search_fields = ['text']

    def get_queryset(self, request):
        """Get with annotations."""
        qs = self.model._default_manager.get_queryset()
        qs = qs.filter(torrents__category=CATEGORY_TV_SHOWS)

        qs = qs.annotate(seeders=Sum('torrents__seeders'))
        qs = qs.annotate(earliest_uploaded_at=Min('torrents__uploaded_at'))

        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    @admin.display(ordering=F('seeders').desc(nulls_last=None))
    def seeders(self, title: Title) -> str:
        """Seeders field."""
        return f'{title.seeders}'

    @admin.display(ordering=F('lastest_uploaded_at').asc(nulls_last=None))
    def lastest_uploaded_at(self, title: Title) -> str:
        """Latest uploaded at field."""
        old = f'{title.lastest_uploaded_at:%Y-%m-%d %H:%I}'
        return f'{old}'

    @admin.display(ordering=F('earliest_uploaded_at').asc(nulls_last=None))
    def earliest_uploaded_at(self, title: Title) -> str:
        """Earliest uploaded at field."""
        old = f'{title.earliest_uploaded_at:%Y-%m-%d %H:%I}'
        return f'{old}'

    @admin.display(ordering=F('num_before').desc(nulls_last=None))
    def num_before(self, title: Title) -> str:
        """Number before field."""
        return title.num_before

    @admin.display(ordering=F('num_after').desc(nulls_last=None))
    def num_after(self, title: Title) -> str:
        """Number after field."""
        return title.num_after

    def torrents(self, title: Title) -> str:
        """Torrents count."""
        return title.torrents.count()

    def last_name(self, title: Title) -> str:
        """Last name field."""
        if last_torrent := title.torrents.order_by('uploaded_at').last():
            url = reverse('admin:main_torrent_changelist')
            return format_html(f'<a href="{url}?title={title.text}&o=-11">{last_torrent.name}</a>')


class Movies(Title):
    class Meta:
        proxy = True
        verbose_name = 'Movie'
        verbose_name_plural = 'Movies'


@admin.register(Movies)
class MoviesAdmin(admin.ModelAdmin):
    list_display = ('seeders', 'earliest_uploaded_at', 'status', 'text', 'torrents', 'last_name')
    # ordering = ('earliest_uploaded_at',)
    actions = [mark_as_skipped_cmd, mark_as_finished_cmd, mark_as_new_cmd]
    # list_filter = ('status',)
    change_list_template = 'main/movies_change_list.html'
    search_fields = ['text']
    list_filter = ['status']

    def get_queryset(self, request):
        """Get with annotations."""
        qs = self.model._default_manager.get_queryset()
        qs = qs.filter(torrents__category=CATEGORY_MOVIES)

        qs = qs.annotate(seeders=Sum('torrents__seeders'))
        qs = qs.annotate(earliest_uploaded_at=Min('torrents__uploaded_at'))

        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    @admin.display(ordering=F('seeders').desc(nulls_last=None))
    def seeders(self, title: Title) -> str:
        """Seeders field."""
        return f'{title.seeders}'

    @admin.display(ordering=F('earliest_uploaded_at').asc(nulls_last=None))
    def earliest_uploaded_at(self, title: Title) -> str:
        """Earliest uploaded at field."""
        old = f'{title.earliest_uploaded_at:%Y-%m-%d %H:%I}'
        return f'{old}'

    def torrents(self, title: Title) -> str:
        """Torrents count."""
        return title.torrents.count()

    def last_name(self, title: Title) -> str:
        """Last name field."""
        if last_torrent := title.torrents.order_by('uploaded_at').last():
            url = reverse('admin:main_torrent_changelist')
            return format_html(f'<a href="{url}?title={title.text}&o=-11">{last_torrent.name}</a>')
