import logging

from django.core.management import BaseCommand
from django.db.models import Count, Max, Min
from django.utils.timezone import now

from main.models import Title
from main.scraper import scrape_1337x_live

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape 1337x pages live using botasaurus and parse results'

    def handle(self, *args, **options):
        logger.info('scraping 1337x live')
        scrape_1337x_live()

        logger.info('updating titles')

        # Delete titles with no torrents in one query
        Title.objects.annotate(torrent_count=Count('torrents')).filter(torrent_count=0).delete()

        # Bulk compute stats in a single query
        titles = list(
            Title.objects.annotate(
                _earliest=Min('torrents__uploaded_at'),
                _latest=Max('torrents__uploaded_at'),
            ).all()
        )
        current = now()
        for title in titles:
            title.earliest_upload_at = title._earliest
            title.latest_upload_at = title._latest
            if title.earliest_upload_at and title.latest_upload_at:
                days_earliest = (current - title.earliest_upload_at).days
                days_latest = (current - title.latest_upload_at).days
                title.priority = days_earliest + days_latest

        Title.objects.bulk_update(
            titles, ['earliest_upload_at', 'latest_upload_at', 'priority'], batch_size=500
        )

        logger.info('done')
