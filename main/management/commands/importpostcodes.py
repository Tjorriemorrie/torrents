import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from main.models import Postcode

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import South African postcodes from ZA.txt into the Postcode model.'

    def handle(self, *args, **options):
        data_file = settings.BASE_DIR / 'ZA.txt'

        if not data_file.exists():
            logger.error(f'ZA.txt not found at: {data_file}')
            raise FileNotFoundError(f'ZA.txt not found at: {data_file}')

        total_lines = 0
        seen_codes = set()
        duplicates = 0

        with data_file.open(encoding='utf-8') as f:
            for line_number, line in enumerate(f, 1):
                total_lines += 1
                parts = line.strip().split('\t')

                if len(parts) == 11:
                    parts.append('')

                if len(parts) != 12:
                    raise ValueError(f'Malformed line {line_number}: {line.strip()}')

                try:
                    code = int(parts[1])
                    area = parts[2]
                    lat = float(parts[-3])
                    lon = float(parts[-2])
                except (ValueError, IndexError) as e:
                    raise ValueError(f'Error parsing line {line_number}: {e}')

                if code in seen_codes:
                    duplicates += 1
                    existing_row = Postcode.objects.get(code=code)
                    logger.error(f'Duplicate: {existing_row} vs {code} ({area}) - {lat} {lon}')
                else:
                    seen_codes.add(code)

                Postcode.objects.update_or_create(
                    code=code, defaults={'area': area, 'latitude': lat, 'longitude': lon}
                )

        logger.info(f'Found {duplicates} duplicate postcodes in the file')
        total_postcodes = Postcode.objects.count()
        logger.info(f'Database row count {total_postcodes} vs file line count {total_lines}')
        logger.info(f'Successfully imported {len(seen_codes)} postcodes from {total_lines} lines.')
