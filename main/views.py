from datetime import timedelta

from django.shortcuts import render
from django.utils.timezone import now

from main.constants import CATEGORY_GAMES, CATEGORY_TV_SHOWS, STATUS_FINISHED
from main.models import Title


def home_view(request):
    """Home view."""
    played_games = (
        Title.objects.filter(status=STATUS_FINISHED, torrents__category=CATEGORY_GAMES)
        .order_by('-status_at', '-updated_at')
        .distinct()
    )
    three_years_ago = now() - timedelta(days=365 * 3)
    old_series = Title.objects.filter(
        torrents__category=CATEGORY_TV_SHOWS, latest_upload_at__lt=three_years_ago
    )
    ctx = {
        'played_games': played_games,
        'old_series': old_series,
    }
    return render(request, 'main/home.html', ctx)
