import logging
from datetime import timedelta

from django.contrib import admin
from django.db.models import F, Max, Min, Count, Q, QuerySet
from django.urls import reverse
from django.utils.html import format_html
from django.utils.timezone import now

from main.constants import STATUS_NEW, STATUS_SKIPPED, CATEGORY_GAMES, CATEGORY_TV_SHOWS, STATUS_FINISHED
from main.models import Torrent, Title
from main.parsing import parse_title

logger = logging.getLogger(__name__)


@admin.action(description='Parse title of torrent')
def parse_title_cmd(modeladmin, request, queryset):
    logger.info('Parsing titles of torrents...')
    torrents = set(t for t in queryset)
    for torrent in torrents:
        parse_title(torrent)


@admin.action(description='Mark as skipped')
def mark_as_skipped_cmd(modeladmin, request, queryset):
    logger.info('Marking as skipped...')
    titles = set(t for t in queryset)
    for title in titles:
        title.status = STATUS_SKIPPED
        title.save()


@admin.action(description='Mark as finished')
def mark_as_finished_cmd(modeladmin, request, queryset):
    logger.info('Marking as finished...')
    titles = set(t for t in queryset)
    for title in titles:
        title.status = STATUS_FINISHED
        title.save()


@admin.register(Torrent)
class TorrentAdmin(admin.ModelAdmin):
    list_display = ('pk', 'title', 'category', 'subcategory', 'seeders', 'leechers', 'size', 'uploader', 'name', 'site', 'uploaded_at')
    list_filter = ('category', 'subcategory')
    ordering = ['-seeders']
    actions = [parse_title_cmd]
    fields = ('title', 'name', 'category', 'subcategory')
    readonly_fields = ('name',)

    change_list_template = 'main/torrent_change_list.html'

    def save_model(self, request, obj, form, change):
        if 'title' in form.changed_data and obj.title.status == STATUS_SKIPPED:
            obj.title.status = STATUS_NEW
            obj.title.save()
        return super().save_model(request, obj, form, change)


@admin.register(Title)
class TitleAdmin(admin.ModelAdmin):
    list_display = ('text', 'status', 'torrents', 'year', 'last_name', 'first_upload', 'last_upload')
    search_fields = ('text',)
    list_filter = ('status',)

    def torrents(self, title: Title) -> str:
        return title.torrents.count()

    @admin.display(ordering=F('last_name').asc(nulls_last=False))
    def last_name(self, title: Title) -> str:
        if last_torrent := title.torrents.order_by('uploaded_at').last():
            url = reverse('admin:main_torrent_changelist')
            return format_html(f'<a href="{url}?title={title.text}&o=-11">{last_torrent.name}</a>')

    @admin.display(ordering=F('last_upload').asc(nulls_last=False))
    def last_upload(self, title: Title) -> str:
        return f'{title.last_upload:%Y-%m-%d %H:%I}'

    @admin.display(ordering=F('first_upload').asc(nulls_last=False))
    def first_upload(self, title: Title) -> str:
        return f'{title.first_upload:%Y-%m-%d %H:%I}'

    def get_queryset(self, request) -> QuerySet:
        qs = self.model._default_manager.get_queryset()
        # qs = qs.annotate(last_upload=ExpressionWrapper(now() - F('oldest_updated_at'), models.FloatField()))
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
    list_display = ('text', 'status', 'year', 'torrents', 'last_name', 'num_before', 'num_after', 'earliest_uploaded_at', 'lastest_uploaded_at')
    ordering = ('-year', 'status',)
    list_filter = ('status',)
    actions = [mark_as_skipped_cmd, mark_as_finished_cmd]

    change_list_template = 'main/pcgames_change_list.html'

    def get_queryset(self, request):
        qs = self.model._default_manager.get_queryset()
        qs = qs.filter(torrents__category=CATEGORY_GAMES)

        one_year = now() - timedelta(days=365)
        two_years = now() - timedelta(days=365*2)

        qs = qs.annotate(lastest_uploaded_at=Max('torrents__uploaded_at'))
        qs = qs.annotate(earliest_uploaded_at=Min('torrents__uploaded_at'))
        qs = qs.filter(earliest_uploaded_at__lt=two_years)

        qs = qs.annotate(num_before=Count('torrents', filter=Q(torrents__uploaded_at__lt=two_years)))
        qs = qs.annotate(num_after=Count('torrents', filter=Q(torrents__uploaded_at__gt=two_years)))

        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    @admin.display(ordering=F('lastest_uploaded_at').asc(nulls_last=False))
    def lastest_uploaded_at(self, title: Title) -> str:
        old = f'{title.lastest_uploaded_at:%Y-%m-%d %H:%I}'
        return f'{old}'

    @admin.display(ordering=F('earliest_uploaded_at').asc(nulls_last=False))
    def earliest_uploaded_at(self, title: Title) -> str:
        old = f'{title.earliest_uploaded_at:%Y-%m-%d %H:%I}'
        return f'{old}'

    @admin.display(ordering=F('num_before').desc(nulls_last=False))
    def num_before(self, title: Title) -> str:
        return title.num_before

    @admin.display(ordering=F('num_after').desc(nulls_last=False))
    def num_after(self, title: Title) -> str:
        return title.num_after

    def torrents(self, title: Title) -> str:
        return title.torrents.count()

    def last_name(self, title: Title) -> str:
        if last_torrent := title.torrents.order_by('uploaded_at').last():
            url = reverse('admin:main_torrent_changelist')
            return format_html(f'<a href="{url}?title={title.text}&o=-11">{last_torrent.name}</a>')


class TvShows(Title):
    class Meta:
        proxy = True
        verbose_name = 'TV Show'
        verbose_name_plural = 'TV Shows'


@admin.register(TvShows)
class TVShowsAdmin(admin.ModelAdmin):
    list_display = ('earliest_uploaded_at', 'series', 'season', 'episode', 'status', 'torrents', 'last_name')
    ordering = ('series', 'season', 'episode')
    actions = [mark_as_skipped_cmd, mark_as_finished_cmd]
    # list_filter = ('status',)
    change_list_template = 'main/tvshows_change_list.html'

    def get_queryset(self, request):
        qs = self.model._default_manager.get_queryset()
        qs = qs.filter(torrents__category=CATEGORY_TV_SHOWS)

        qs = qs.annotate(earliest_uploaded_at=Min('torrents__uploaded_at'))

        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    @admin.display(ordering=F('lastest_uploaded_at').asc(nulls_last=False))
    def lastest_uploaded_at(self, title: Title) -> str:
        old = f'{title.lastest_uploaded_at:%Y-%m-%d %H:%I}'
        return f'{old}'

    @admin.display(ordering=F('earliest_uploaded_at').asc(nulls_last=False))
    def earliest_uploaded_at(self, title: Title) -> str:
        old = f'{title.earliest_uploaded_at:%Y-%m-%d %H:%I}'
        return f'{old}'

    @admin.display(ordering=F('num_before').desc(nulls_last=False))
    def num_before(self, title: Title) -> str:
        return title.num_before

    @admin.display(ordering=F('num_after').desc(nulls_last=False))
    def num_after(self, title: Title) -> str:
        return title.num_after

    def torrents(self, title: Title) -> str:
        return title.torrents.count()

    def last_name(self, title: Title) -> str:
        if last_torrent := title.torrents.order_by('uploaded_at').last():
            url = reverse('admin:main_torrent_changelist')
            return format_html(f'<a href="{url}?title={title.text}&o=-11">{last_torrent.name}</a>')
