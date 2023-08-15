import difflib
import logging
import re
from pathlib import Path
from time import sleep

import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.utils.timezone import now, make_aware
from retry import retry

from main.constants import SITE_1337X, CATEGORY_GAMES, SUBCATEGORY_H264, SUBCATEGORY_BOLLYWOOD, \
    SUBCATEGORY_DUBS, SUBCATEGORY_HEVC, SUBCATEGORY_PCGAMES, SITE_RARBG, \
    CATEGORY_MOVIES, SUBCATEGORY_HD_MOVIES, SUBCATEGORY_HD_TV, CATEGORY_TV_SHOWS, SUBCATEGORY_SD_TV, \
    SUBCATEGORY_DIVX_TV, SUBCATEGORY_HEVC_TV, SUBCATEGORY_DVD, SUBCATEGORY_UHD, STATUS_SKIPPED, SUBCATEGORY_DIVX_MOVIES
from main.models import Torrent, Title
from torrents.settings import BASE_DIR

logger = logging.getLogger(__name__)
sleep_time = 0
last_url = None


class RetryRequestsError(Exception):
    """Error indicating to retry request."""


@retry((RetryRequestsError,), delay=5, jitter=1, max_delay=60)
def get(url: str) -> requests.Response:
    global sleep_time
    global last_url
    if last_url == url:
        sleep_time = round(sleep_time + 0.5, 3)
        logger.info(f'Increased sleep time to {sleep_time}')
    elif sleep_time:
        sleep_time = round(sleep_time - 0.005, 3)
    last_url = url
    sleep(sleep_time)

    try:
        res = requests.get(url)
    except Exception as exc:
        logger.warning(f'Connection error! {exc}')
        raise RetryRequestsError() from exc
    if res.status_code == 429:
        logger.warning(f'Too many requests! {url}')
        raise RetryRequestsError()
    elif res.status_code >= 500:
        logger.warning(f'Server error! {url}')
        raise RetryRequestsError()
    res.raise_for_status()
    return res


def scrape_sites():
    logger.info('Scraping sites...')
    scrape_1337x()
    scrape_rarbg()
    logger.info('sites scraped.')


def scrape_1337x():
    logger.info(f'Scraping 1337x...')
    file_paths = Path(BASE_DIR / '1337x_files').glob('*')
    for file_path in file_paths:
        if not str(file_path).endswith('html'):
            continue
        data = scrape_1337x_page(file_path)
        for ix, item in enumerate(data):
            try:
                torrent = Torrent.objects.get(url=item['url'])
                torrent.seeders = item['seeders']
                torrent.leechers = item['leechers']
                torrent.save()
            except Torrent.DoesNotExist:
                torrent = Torrent.objects.create(
                    site=SITE_1337X,
                    **item
                )
            # auto-create title for TV shows
            auto_add_title(torrent)
            logger.info(f'{ix}: {torrent}')
    logger.info('finished scraping 1337x')


def scrape_1337x_page(file_path):
    data = []
    with open(file_path, 'r', errors='ignore') as fp:
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
        elif '/sub/1/0' in str(cols[0]):
            subcategory = SUBCATEGORY_DVD
            category = CATEGORY_MOVIES
        elif '/sub/76/0' in str(cols[0]):
            subcategory = SUBCATEGORY_UHD
            category = CATEGORY_MOVIES
        elif '/sub/2/0' in str(cols[0]):
            subcategory = SUBCATEGORY_DIVX_MOVIES
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

        # games
        elif '/sub/10/0' in str(cols[0]):
            subcategory = SUBCATEGORY_PCGAMES
            category = CATEGORY_GAMES
        elif any([
            '/sub/43/0' in str(cols[0]),  # ps3
            '/sub/77/0' in str(cols[0]),  # ps4
            '/sub/13/0' in str(cols[0]),  # xbox
            '/sub/14/0' in str(cols[0]),  # xbox 360
            '/sub/82/0' in str(cols[0]),  # switch
            '/sub/67/0' in str(cols[0]),  # unknown platform
            '/sub/34/0' in str(cols[0]),  # tutorials
            '/sub/35/0' in str(cols[0]),  # sounds
            '/sub/36/0' in str(cols[0]),  # ebooks
        ]):
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
                    **item
                )
            logger.info(f'{ix}: {torrent}')
    logger.info(f'finished scraping {SITE_RARBG}')


def scrape_rarbg_page(file_path):
    data = []
    with open(file_path, 'r') as fp:
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
    assert len(by_kind) == original_len
    return by_kind


def expand_on_name_deprecated(category, item):
    # clean bad ending
    while any([
        item['name'].endswith('.'),
        item['name'].endswith('-'),
    ]):
        item['name'] = item['name'].rstrip(item['name'][-1])

    # strip pirate
    if item['name'].endswith('-GalaxyRG'):
        item['name'] = item['name'].rstrip('-GalaxyRG')
        item['pirate'] = 'GalaxyRG'
    if item['name'].endswith('GalaxyR'):
        item['name'] = item['name'].rstrip('GalaxyR')
        item['pirate'] = 'GalaxyRG'
    if item['name'].endswith(' - ProLover'):
        item['name'] = item['name'].rstrip(' - ProLover')
        item['pirate'] = 'ProLover'
    if item['name'].endswith(' ~ BunnyJMB'):
        item['name'] = item['name'].rstrip(' ~ BunnyJMB')
        item['pirate'] = 'BunnyJMB'
    if item['name'].endswith('-iDiOTS'):
        item['name'] = item['name'].rstrip('-iDiOTS')
        item['pirate'] = 'iDiOTS'
    if item['name'].endswith(' - mkvAnime'):
        item['name'] = item['name'].rstrip(' - mkvAnime')
        item['pirate'] = 'mkvAnime'
    if item['name'].endswith('-themoviesboss'):
        item['name'] = item['name'].rstrip('-themoviesboss')
        item['pirate'] = 'themoviesboss'
    if item['name'].endswith('-the'):
        item['name'] = item['name'].rstrip('-the')
        item['pirate'] = 'themoviesboss'
    if item['name'].endswith('- QRips'):
        item['name'] = item['name'].rstrip(' - QRips')
        item['pirate'] = 'QRips'
    if item['name'].endswith(' Ads Free - HushRips'):
        item['name'] = item['name'].rstrip(' Ads Free - HushRips')
        item['pirate'] = 'HushRips'
    if item['name'].endswith('-NAISU'):
        item['name'] = item['name'].rstrip('-NAISU')
        item['pirate'] = 'Naisu'

    # parse name
    this_year = now().year
    item['title'] = []
    item['name'] = item['name'].replace('(', '')
    item['name'] = item['name'].replace(')', '')
    item['name'] = item['name'].replace('[', '')
    item['name'] = item['name'].replace(']', '')
    item['name'] = item['name'].replace(',', ' ')
    item['name'] = item['name'].replace('-', '.')
    name_parts = item['name'].split('.')
    if len(name_parts) < 3:
        name_parts = item['name'].split(' ')
    if len(name_parts) < 3:
        raise ValueError(f'Could not split name: {item["name"]}')
    audio_suffix = ''
    # https://en.wikipedia.org/wiki/Pirated_movie_release_types
    for part in reversed(name_parts):
        if not part:
            continue
        elif part in ['H264', 'x264', 'HEVC', 'x265']:
            item['video_codec'] = part
        # first video part
        elif part in ['HC', 'HDCAM', 'Cam Cleaned', 'WebRip', 'WEBRip', 'WEBDL', 'WEB-DL', 'TELESYNC', 'HDTC', 'HDTS', 'BluRay', 'Rip']:
            if item.get('source'):
                if item['source'] == 'HDCAM':
                    continue
                raise ValueError('source already set!')
            part = 'HDCAM' if part in ['HC', 'TELESYNC', 'HDTC', 'HDTS', 'Cam Cleaned'] else part
            part = 'WebRip' if part in ['WEBDL', 'WEB-DL', 'WEBRip', 'Rip'] else part
            item['source'] = item.get('source', '') != 'HDCAM' and part
        # second video part that can overwrite source
        elif part in [
            'DSNP',  # disney
            'AMZN',   # amazon prime
            'NF',   # netflix
            'ZEE5', 'ZEE',  # zee5
            'HULU'  # hulu
        ]:
            part = 'ZEE5' if part in ['ZEE'] else part
            item['source'] = item.get('source', '') != 'HDCAM' and part
        elif part in ['1080p', '720p']:
            item['resolution'] = part
        elif part in ['1', '2.0', '5.1', 'Atmos', '2', '5']:
            if part == '2':
                part = '2.0'
            if part == '5':
                part = '5.1'
            audio_suffix = ' ' if part != '1' else '.'
            audio_suffix += part
        elif part in ['DDP5', 'DD5', 'DD', 'AAC', 'AC3']:
            item['audio_codec'] = part + audio_suffix
        elif part in ['ESub', 'ESubs']:
            item['subtitle'] = part
        elif part in ['Hindi', 'HINDI']:
            item['language'] = part
        elif part.endswith('0MB') or part.endswith('GB'):
            continue
        elif part in [
            'No', 'LOGO', 'V2', 'ORG', '0', 'S-Print', 'HQ', 'Multi', 'WEB', 'DL', 'H', '10Bit',
            'Tel', 'Dub', 'UN', 'Hin', 'Aud', 'Dual', 'Free', 'Ads']:
            continue  # junk
        elif 'year' not in item and len(part) == 4:
            year = int(part)
            if 1950 <= year <= this_year:
                item['year'] = year
            else:
                raise ValueError(f'Unknown year {year}')
        elif 'year' in item:
            item['title'].append(part)
        else:
            raise NotImplementedError(f'Unknown part {part}')
    item['title'] = ' '.join(reversed(item['title']))
    item['title'] = item['title'].replace(' :', ':')
    return item


def auto_add_title(torrent: Torrent):
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
                })
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
                    })
            else:

                matches = re.search(r'(Formula.1.\d{4}.Round.\d\d.\w+)', torrent.name)
                if matches:
                    name = matches.group(0).replace('.', ' ').strip()
                    title, _ = Title.objects.get_or_create(text=name)
                else:

                    matches = re.search(r'(.*?\d+)', torrent.name)
                    if matches:
                        name = matches.group(0).replace('.', ' ').strip()
                        title, _ = Title.objects.get_or_create(text=name)
                    else:
                        raise ValueError('unknown format')
        torrent.title = title
        torrent.save()

    elif torrent.category == CATEGORY_MOVIES and not torrent.title:
        raw_name = torrent.name.replace('.', ' ').replace(
            '-', ' ').replace(
            '[', '').replace(']', '').replace(
            '(', '').replace(')', '').strip()
        matches = re.search(r'(.+\s(19|20)\d{2}).*', raw_name, re.I)
        if matches:
            name = matches.group(1)
            title, _ = Title.objects.get_or_create(text=name)
        else:
            title, _ = Title.objects.get_or_create(text='junk')
        # skip these
        skip_list = ['hindi', 'hdts', 'hdtc', '720p', 'hd-cam', 'ita eng', 'camrip']
        if any(w in raw_name.lower() for w in skip_list):
            title.status = STATUS_SKIPPED
            title.save()
        torrent.title = title
        torrent.save()

