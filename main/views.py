from django.db.models import Max
from django.shortcuts import redirect, render
from django.urls import reverse

from main.constants import CATEGORY_GAMES, CATEGORY_MOVIES, CATEGORY_TV_SHOWS, STATUS_FINISHED
from main.models import Title, Torrent
from main.selectors import list_old_tv, list_titles_without_torrents


def home_view(request):
    """Home view."""
    titles_without_torrents = list_titles_without_torrents()
    old_tv = list_old_tv()
    count_movies = Torrent.objects.filter(category=CATEGORY_MOVIES).count()
    count_series = Torrent.objects.filter(category=CATEGORY_TV_SHOWS).count()
    count_games = Torrent.objects.filter(category=CATEGORY_GAMES).count()
    recent_games = (
        Title.objects.filter(torrents__category=CATEGORY_GAMES, status=STATUS_FINISHED)
        .values('text')
        .annotate(latest_upload=Max('earliest_upload_at'))
        .order_by('-latest_upload')[:5]
    )
    ctx = {
        # 'played_games': played_games,
        'old_tv': old_tv,
        'titles_without_torrents': titles_without_torrents,
        'count_movies': count_movies,
        'count_series': count_series,
        'count_games': count_games,
        'recent_games': list(recent_games)[::-1],
    }
    return render(request, 'main/home.html', ctx)


def clear_tv_view(request):
    """Clear old tv torrents."""
    old_tv = list_old_tv()
    old_tv.delete()
    titles_without_torrents = list_titles_without_torrents()
    titles_without_torrents.delete()
    return redirect(reverse('home_view'))
