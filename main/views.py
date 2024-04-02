from django.shortcuts import render

from main.constants import CATEGORY_GAMES, STATUS_FINISHED
from main.models import Title


def home_view(request):
    """Home view."""
    played_games = (
        Title.objects.filter(status=STATUS_FINISHED, torrents__category=CATEGORY_GAMES)
        .order_by('-status_at', '-updated_at')
        .distinct()
    )
    ctx = {
        'played_games': played_games,
    }
    return render(request, 'main/home.html', ctx)
