from datetime import timedelta

from django.db.models import DurationField, ExpressionWrapper, F, Max, Min, QuerySet
from django.utils import timezone
from django.utils.timezone import now

from main.constants import CATEGORY_GAMES, CATEGORY_MOVIES, CATEGORY_TV_SHOWS, STATUS_FINISHED
from main.models import Title, Torrent


def list_titles_without_torrents():
    """Get empty titles."""
    titles_without_torrents = Title.objects.filter(torrents__isnull=True)
    return titles_without_torrents


def list_old_tv():
    """List old tv."""
    time_ago = timezone.now() - timedelta(days=365 * 2)
    old_tv = Torrent.objects.filter(
        created_at__lt=time_ago, category__in=[CATEGORY_MOVIES, CATEGORY_TV_SHOWS]
    )
    return old_tv


def list_recent_games() -> QuerySet[Title]:
    """List recent games."""
    recent_games = (
        Title.objects.filter(
            torrents__category=CATEGORY_GAMES,
            status=STATUS_FINISHED,
        )
        .annotate(
            earliest_upload=Min('torrents__uploaded_at'),
            latest_upload=Max('torrents__uploaded_at'),
        )
        .annotate(
            days_since_status=ExpressionWrapper(
                now() - F('status_at'),
                output_field=DurationField(),
            )
        )
        .order_by('-status_at')[:10]
    )
    return recent_games
