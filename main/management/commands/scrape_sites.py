import logging

from django.core.management import BaseCommand

from main.models import Title
from main.scraper import scrape_sites

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape torrent sites'

    def handle(self, *args, **options):
        scrape_sites()
        titles = Title.objects.filter().all()
        for title in titles:
            if not title.torrents.count():
                title.delete()
                continue
            title.update_stats()
            title.save()