import logging
from math import asin, cos, radians, sin, sqrt

from django.core.management.base import BaseCommand
from django.db.models import Count

from main.models import Distance, Postcode

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000  # Adjust as needed


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


class Command(BaseCommand):
    help = 'Populate the Distance table with km between each unique pair of Postcodes.'

    def handle(self, *args, **options):
        postcodes = list(
            Postcode.objects.filter(level__in=['suburb', 'neighbourhood', 'town']).all()
        )
        total_pairs = len(postcodes) * (len(postcodes) - 1) // 2
        logger.info(f'Calculating distances for {total_pairs:,} postcode pairs...')

        level_counts = (
            Postcode.objects.values('level')
            .annotate(count=Count('id'))
            .order_by('-count')  # Optional: sort by highest count first
        )
        for entry in level_counts:
            logger.info(f"{entry['level'] or '[None]'}: {entry['count']}")

        batch = []
        count = 0

        for i, a in enumerate(postcodes):
            for b in postcodes[i + 1 :]:
                if a.id > b.id:
                    a, b = b, a

                # Check if this distance already exists
                if Distance.objects.filter(postcode_a=a, postcode_b=b).exists():
                    continue

                km = haversine(a.latitude, a.longitude, b.latitude, b.longitude)
                batch.append(Distance(postcode_a=a, postcode_b=b, km=round(km, 3)))
                count += 1

                if len(batch) >= BATCH_SIZE:
                    Distance.objects.bulk_create(batch)
                    logger.info(f'Inserted {count:,} distances so far...')
                    batch.clear()

        # Final flush
        if batch:
            Distance.objects.bulk_create(batch)
            logger.info(f'Inserted final {len(batch):,} distances.')

        logger.info(f'Completed populating distances. Total inserted: {count:,}')
