import logging
from collections import Counter

from main.models import Torrent


logger = logging.getLogger(__name__)


def parse_title(torrent: Torrent):
    logger.info(f'parsing title for {torrent}')
    title = torrent.name.title()

    # replace underscores
    cntr = Counter(title)
    if cntr['_'] > cntr[' ']:
        title = title.replace('_', ' ')

    # stop when getting brackets
    if (ix := title.find('(')) != -1:
        title = title[:ix].strip()

    torrent.title = title
    torrent.save()
