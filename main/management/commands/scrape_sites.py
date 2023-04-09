import logging

from django.core.management import BaseCommand

from main.scraper import scrape_sites

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape torrent sites'

    def handle(self, *args, **options):
        scrape_sites()
