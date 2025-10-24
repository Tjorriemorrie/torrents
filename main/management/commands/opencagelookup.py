import logging
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from main.models import Postcode

logger = logging.getLogger(__name__)
BASE_URL = 'https://api.opencagedata.com/geocode/v1/json'


def latlng_precision(result):
    try:
        lat = result['geometry']['lat']
        lng = result['geometry']['lng']
        lat_prec = len(str(lat).split('.')[1]) if '.' in str(lat) else 0
        lng_prec = len(str(lng).split('.')[1]) if '.' in str(lng) else 0
        return lat_prec + lng_prec
    except Exception:
        return 0


class Command(BaseCommand):
    help = 'Update or create Postcode entries using OpenCage API for postcodes 0001–4000'

    def handle(self, *args, **options):
        key = getattr(settings, 'OPENCAGE_API_KEY', None)
        if not key:
            raise RuntimeError('OPENCAGE_API_KEY is not set in settings.')

        # Find the last postcode where opencage=True
        last_updated = Postcode.objects.filter(opencage=True).order_by('-code').first()
        start_code = (last_updated.code + 1) if last_updated else 1

        logger.info(f'Starting update from postcode {start_code:04d}')

        updated = 0
        skipped = 0

        for code in range(start_code, 9_999):
            code_str = f'{code:04d}'

            # Skip if already updated
            existing = Postcode.objects.filter(code=code, opencage=True).first()
            if existing:
                continue

            query = f'{code_str}, south africa'
            params = {
                'q': query,
                'key': key,
                'language': 'en',
                'no_annotations': 1,
                'pretty': 0,
            }

            # logger.info(f"Looking up postcode {code_str}...")

            try:
                response = requests.get(BASE_URL, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logger.warning(f'Request failed for {code_str}: {e}')
                raise

            postcode_results = [
                r
                for r in data.get('results', [])
                if r.get('components', {}).get('_type') == 'postcode'
            ]

            postcode_results.sort(key=latlng_precision, reverse=True)
            result = postcode_results[0] if postcode_results else None

            if not result:
                logger.info(f'No valid postcode result found for {code_str}')
                skipped += 1
                continue

            geometry = result.get('geometry', {})
            lat = geometry.get('lat')
            lng = geometry.get('lng')
            components = result.get('components', {})
            level = ''
            area = ''

            for lvl_key in [
                'suburb',
                'neighbourhood',
                'town',
                'village',
                'city_district',
                'city',
                'municipality',
                'county',
                'state_district',
                'state',
                'region',
                'province',
                'country',
            ]:
                value = components.get(lvl_key)
                if value:
                    area = value
                    level = lvl_key
                    break

            if lat is None or lng is None:
                logger.warning(f'Missing lat/lng for {code_str}')
                continue

            postcode_obj, created = Postcode.objects.update_or_create(
                code=code,
                defaults={
                    'latitude': lat,
                    'longitude': lng,
                    'area': area,
                    'level': level,
                    'opencage': True,
                },
            )

            logger.info(
                f"{'Created' if created else 'Updated'} postcode {code_str} {area} at {lat},{lng}"
            )
            updated += 1
            time.sleep(1.2)  # Stay under OpenCage free tier limits

        logger.info(f'Finished. Updated/created: {updated}, Skipped: {skipped}')
