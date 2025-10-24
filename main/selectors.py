from datetime import timedelta

from django.utils import timezone

from main.constants import CATEGORY_MOVIES, CATEGORY_TV_SHOWS
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
