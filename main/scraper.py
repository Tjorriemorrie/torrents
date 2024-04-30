import difflib
import logging
import re
from pathlib import Path
from time import sleep

import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.utils.timezone import make_aware
from retry import retry

from main.constants import (
    CATEGORY_GAMES,
    CATEGORY_MOVIES,
    CATEGORY_TV_SHOWS,
    SITE_1337X,
    SITE_RARBG,
    STATUS_NEW,
    STATUS_SKIPPED,
    SUBCATEGORY_BOLLYWOOD,
    SUBCATEGORY_DIVX_MOVIES,
    SUBCATEGORY_DIVX_TV,
    SUBCATEGORY_DUBS,
    SUBCATEGORY_DVD,
    SUBCATEGORY_H264,
    SUBCATEGORY_HD_MOVIES,
    SUBCATEGORY_HD_TV,
    SUBCATEGORY_HEVC,
    SUBCATEGORY_HEVC_TV,
    SUBCATEGORY_MP4,
    SUBCATEGORY_PCGAMES,
    SUBCATEGORY_SD_TV,
    SUBCATEGORY_UHD,
)
from main.models import Title, Torrent
from torrents.settings import BASE_DIR

logger = logging.getLogger(__name__)
sleep_time = 0
last_url = None


class RetryRequestsError(Exception):
    """Error indicating to retry request."""


@retry((RetryRequestsError,), delay=5, jitter=1, max_delay=60)
def get(url: str) -> requests.Response:
    """Get url with backoff."""
    global sleep_time  # noqa PLW0603
    global last_url  # noqa PLW0603
    if last_url == url:
        sleep_time = round(sleep_time + 0.5, 3)
        logger.info(f'Increased sleep time to {sleep_time}')
    elif sleep_time:
        sleep_time = round(sleep_time - 0.005, 3)
    last_url = url
    sleep(sleep_time)

    try:
        res = requests.get(url, timeout=30)
    except Exception as exc:
        logger.warning(f'Connection error! {exc}')
        raise RetryRequestsError() from exc
    if res.status_code == requests.codes.too_many:
        logger.warning(f'Too many requests! {url}')
        raise RetryRequestsError()
    elif res.status_code >= requests.codes.server_error:
        logger.warning(f'Server error! {url}')
        raise RetryRequestsError()
    res.raise_for_status()
    return res


def scrape_sites():
    """Scrape sites."""
    logger.info('Scraping sites...')
    scrape_1337x()
    # scrape_rarbg()
    logger.info('sites scraped.')


def scrape_1337x():
    """Scrape all 1337x pages."""
    logger.info('Scraping 1337x...')
    file_paths = Path(BASE_DIR / '1337x_files').glob('*')
    for file_path in file_paths:
        if not str(file_path).endswith('html'):
            continue
        # if 'topmovies' not in str(file_path):
        #     continue
        data = scrape_1337x_page(file_path)
        for ix, item in enumerate(data):
            try:
                torrent = Torrent.objects.get(url=item['url'])
                torrent.seeders = item['seeders']
                torrent.leechers = item['leechers']
                torrent.save()
            except Torrent.DoesNotExist:
                torrent = Torrent.objects.create(site=SITE_1337X, **item)
            # auto-create title for TV shows
            auto_add_title(torrent)
            logger.info(f'{ix}: {torrent}')
    logger.info('finished scraping 1337x')


def scrape_1337x_page(file_path):  # noqa PLR0915 PLR0912
    """Scrape list of torrents from 1337x page."""
    data = []
    with Path.open(file_path, errors='ignore') as fp:
        content = fp.read()
    html = BeautifulSoup(content, 'html.parser')

    rows = html.find('table', class_='table-list').find_all('tr')
    for row in rows[1:]:
        cols = row.find_all('td')

        # subcategory
        # movies
        if '/sub/54/0' in str(cols[0]):
            subcategory = SUBCATEGORY_H264
            category = CATEGORY_MOVIES
        elif '/sub/70/0' in str(cols[0]):
            subcategory = SUBCATEGORY_HEVC
            category = CATEGORY_MOVIES
        elif '/sub/73/0' in str(cols[0]):
            subcategory = SUBCATEGORY_BOLLYWOOD
            category = CATEGORY_MOVIES
        elif '/sub/42/0' in str(cols[0]):
            subcategory = SUBCATEGORY_HD_MOVIES
            category = CATEGORY_MOVIES
        elif '/sub/4/0' in str(cols[0]):
            subcategory = SUBCATEGORY_DUBS
            category = CATEGORY_MOVIES
        elif '/sub/1/0' in str(cols[0]) or '/sub/5/0' in str(cols[0]):
            subcategory = SUBCATEGORY_DVD
            category = CATEGORY_MOVIES
        elif '/sub/76/0' in str(cols[0]):
            subcategory = SUBCATEGORY_UHD
            category = CATEGORY_MOVIES
        elif '/sub/2/0' in str(cols[0]):
            subcategory = SUBCATEGORY_DIVX_MOVIES
            category = CATEGORY_MOVIES
        elif '/sub/55/0' in str(cols[0]):
            subcategory = SUBCATEGORY_MP4
            category = CATEGORY_MOVIES

        # tv
        elif '/sub/41/0' in str(cols[0]):
            subcategory = SUBCATEGORY_HD_TV
            category = CATEGORY_TV_SHOWS
        elif '/sub/75/0' in str(cols[0]):
            subcategory = SUBCATEGORY_SD_TV
            category = CATEGORY_TV_SHOWS
        elif '/sub/6/0' in str(cols[0]):
            subcategory = SUBCATEGORY_DIVX_TV
            category = CATEGORY_TV_SHOWS
        elif '/sub/71/0' in str(cols[0]):
            subcategory = SUBCATEGORY_HEVC_TV
            category = CATEGORY_TV_SHOWS
        elif '/sub/48/0' in str(cols[0]):
            subcategory = SUBCATEGORY_DIVX_TV
            category = CATEGORY_TV_SHOWS
        elif any(
            [
                '/sub/74/0' in str(cols[0]),  # cartoon
            ]
        ):
            continue

        # games
        elif '/sub/10/0' in str(cols[0]):
            subcategory = SUBCATEGORY_PCGAMES
            category = CATEGORY_GAMES
        elif any(
            [
                '/sub/11/0' in str(cols[0]),  # ps2
                '/sub/12/0' in str(cols[0]),  # psp
                '/sub/13/0' in str(cols[0]),  # xbox
                '/sub/14/0' in str(cols[0]),  # xbox 360
                '/sub/17/0' in str(cols[0]),  # other
                '/sub/34/0' in str(cols[0]),  # tutorials
                '/sub/35/0' in str(cols[0]),  # sounds
                '/sub/36/0' in str(cols[0]),  # ebooks
                '/sub/43/0' in str(cols[0]),  # ps3
                '/sub/44/0' in str(cols[0]),  # wii
                '/sub/45/0' in str(cols[0]),  # ds
                '/sub/56/0' in str(cols[0]),  # android
                '/sub/67/0' in str(cols[0]),  # unknown platform
                '/sub/72/0' in str(cols[0]),  # 3DS
                '/sub/77/0' in str(cols[0]),  # ps4
                '/sub/82/0' in str(cols[0]),  # switch
            ]
        ):
            continue
        else:
            raise ValueError(f'unknown subcategory: {cols[0]}')

        # category
        if not category or not subcategory:
            raise ValueError(f'Unknown category for sub {cols[0]}')

        # name
        try:
            name = cols[0].find_all('a')[1]
        except IndexError:
            name = cols[0].find_all('a')[0]
        name = name.text

        # url
        try:
            url = cols[0].find_all('a')[1]
        except IndexError:
            url = cols[0].find_all('a')[0]
        url = f'https://1337x.to{url["href"]}'

        # seeders
        seeders = int(cols[1].text)

        # leechers
        leechers = int(cols[2].text)

        # upload date
        uploaded_at = make_aware(parse(cols[3].text))

        # size
        size_txt = cols[4].find(text=True)
        size = size_txt_to_int(size_txt)

        # uploader
        uploader = cols[5].text

        item = {
            'category': category,
            'subcategory': subcategory,
            'name': name,
            'url': url,
            'seeders': seeders,
            'leechers': leechers,
            'uploaded_at': uploaded_at,
            'size': size,
            'uploader': uploader,
        }
        data.append(item)
    logger.info(f'finished scraping {file_path} with {len(data)} torrents found')
    return data


def scrape_1337x_detail_page(item):
    """Scrape details from 1337x page."""
    logger.info(f'Getting detail page for {item}')
    res = get(item['url'])
    html = BeautifulSoup(res.content, 'html.parser')
    anchors = html.find_all('a')
    for anchor in anchors:
        if anchor['href'].startswith('magnet'):
            magnet = anchor['href']
            return magnet
    raise ValueError(f'Could not find magnet link: {item["url"]}')


def scrape_rarbg():
    """Scrape rarbg."""
    logger.info(f'Scraping {SITE_RARBG}...')
    file_paths = Path(BASE_DIR / 'rarbg_files').glob('*')
    for file_path in file_paths:
        if not str(file_path).endswith('html'):
            continue
        data = scrape_rarbg_page(file_path)
        for ix, item in enumerate(data):
            try:
                torrent = Torrent.objects.get(url=item['url'])
                torrent.site = SITE_RARBG
                torrent.seeders = item['seeders']
                torrent.leechers = item['leechers']
                torrent.save()
            except Torrent.DoesNotExist:
                torrent = Torrent.objects.create(
                    site=SITE_RARBG,
                    category=CATEGORY_GAMES,
                    subcategory=SUBCATEGORY_PCGAMES,
                    **item,
                )
            logger.info(f'{ix}: {torrent}')
    logger.info(f'finished scraping {SITE_RARBG}')


def scrape_rarbg_page(file_path):
    """Scrape rarbg page."""
    data = []
    with Path.open(file_path) as fp:
        content = fp.read()
    html = BeautifulSoup(content, 'html.parser')

    try:
        rows = html.find('table', class_='lista2t').find_all('tr')
    except AttributeError as exc:
        raise ValueError(f'with file {file_path}') from exc

    for row in rows[1:]:
        cols = row.find_all('td')

        # name
        name = cols[1].text

        # url
        url_suffix = cols[1].find('a')['href']
        url = f'https://rarbgtor.org{url_suffix}'

        # upload date
        uploaded_at = make_aware(parse(cols[2].text))

        # size
        size_txt = cols[3].text
        size = size_txt_to_int(size_txt)

        # seeders
        seeders = int(cols[4].text)

        # leechers
        leechers = int(cols[5].text)

        # uploader
        uploader = cols[7].text

        item = {
            'name': name,
            'url': url,
            'uploaded_at': uploaded_at,
            'size': size,
            'seeders': seeders,
            'leechers': leechers,
            'uploader': uploader,
        }
        data.append(item)
    logger.info(f'finished scraping {file_path} with {len(data)} torrents found')
    return data


##########################################################################################
# Helpers
##########################################################################################


def size_txt_to_int(size_txt):
    """Change size text to integer."""
    val, exp = size_txt.split(' ')
    val = val.replace(',', '')
    if exp == 'GB':
        size = float(val) * 1_000_000_000
    elif exp == 'MB':
        size = float(val) * 1_000_000
    elif exp == 'KB':
        size = float(val) * 1_000
    else:
        raise NotImplementedError(f'Unknown exp {exp}')
    return size


def make_it_seem_right(torrents):
    """Make it seem right."""
    original_len = len(torrents)
    current = torrents.pop(0)
    by_kind = [current]
    while len(torrents):
        closest = difflib.get_close_matches(current['title'], [t['title'] for t in torrents], n=1)
        if closest:
            current = [t for t in torrents if t['title'] == closest[0]][0]
            torrents = [t for t in torrents if t['title'] != closest[0]]
        else:
            current = torrents.pop(0)

        by_kind.append(current)
    assert len(by_kind) == original_len  # noqa S101
    return by_kind


def auto_add_title(torrent: Torrent):  # noqa PLR0912
    """Parse titles for torrents."""
    if torrent.category == CATEGORY_TV_SHOWS and not torrent.title:
        matches = re.search(r'(.*)S(\d\d)E(\d\d)', torrent.name, re.I)
        if matches:
            series = matches.group(1).replace('.', ' ').strip()
            season = int(matches.group(2))
            episode = int(matches.group(3))
            name = f'{series} S{season:02d}E{episode:02d}'
            title, _ = Title.objects.get_or_create(
                text=name,
                defaults={
                    'series': series,
                    'season': season,
                    'episode': episode,
                },
            )
        else:
            matches = re.search(r'(.*)S(\d\d)', torrent.name, re.I)
            if matches:
                series = matches.group(1).replace('.', ' ').strip()
                season = int(matches.group(2))
                name = f'{series} S{season:02d}'
                title, _ = Title.objects.get_or_create(
                    text=name,
                    defaults={
                        'series': series,
                        'season': season,
                    },
                )
            else:
                matches = re.search(r'(Formula.1.\d{4}.Round.\d\d.\w+)', torrent.name)
                if matches:
                    name = matches.group(0).replace('.', ' ').strip()
                    title, _ = Title.objects.get_or_create(text=name)
                else:
                    name = torrent.name
                    title, _ = Title.objects.get_or_create(text=name)
        torrent.title = title
        torrent.save()

    elif torrent.category == CATEGORY_MOVIES and not torrent.title:
        raw_name = (
            torrent.name.replace('.', ' ')
            .replace('-', ' ')
            .replace('[', '')
            .replace(']', '')
            .replace('(', '')
            .replace(')', '')
            .strip()
        )
        matches = re.search(r'(.+\s(19|20)\d{2}).*', raw_name, re.I)
        if matches:
            name = matches.group(1)
            title, _ = Title.objects.get_or_create(text=name)
            title.status = STATUS_NEW
        else:
            name = torrent.name
            title, _ = Title.objects.get_or_create(text=name)

        # skip these
        skip_list = [
            'hindi',
            'hdts',
            'hdtc',
            '720p',
            '2160p',
            'hd-cam',
            'ita eng',
            ' ita ',
            'camrip',
        ]
        if any(w in raw_name.lower() for w in skip_list):
            title.status = STATUS_SKIPPED
        else:
            title.status = STATUS_NEW
        title.save()

        torrent.title = title
        torrent.save()
