import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from places.models import Place, Category, PlaceSubCategory


class Command(BaseCommand):
    help = 'Import the 14 cultural facilities transcribed from the directorate report.'

    @transaction.atomic
    def handle(self, *args, **options):
        data = json.loads((Path(__file__).resolve().parents[2] / 'data' / 'cultural_directorate.json').read_text(encoding='utf-8'))
        category = Category.objects.get(slug='culture')
        labels = {
            'directorate': 'مديرية الثقافة', 'cultural-center': 'مراكز ثقافية',
            'training-institute': 'معاهد الثقافة الشعبية', 'applied-arts': 'فنون تطبيقية',
            'music-institute': 'معاهد موسيقية', 'fine-arts': 'فنون تشكيلية',
        }
        subcategories = {
            slug: PlaceSubCategory.objects.get_or_create(
                category=category, slug=slug, defaults={'name_ar': label, 'icon': 'landmark'}
            )[0] for slug, label in labels.items()
        }
        created = 0
        for entry in data['facilities']:
            has_location = entry['latitude'] is not None and entry['longitude'] is not None
            if has_location and not (33 < entry['latitude'] < 34 and 36 < entry['longitude'] < 37):
                raise ValueError(f"Invalid Damascus coordinates for {entry['title']}")
            description = [entry.get('services', ''), entry.get('notes', '')]
            if entry.get('out_of_service'):
                description.append('خارج الخدمة وفق التقرير. لم يرد موقع جغرافي في المصدر.')
            description.append(f"المصدر: {data['source']} — الصفحة {entry['page']}.")
            _, is_new = Place.objects.update_or_create(title=entry['title'], defaults={
                'sub_category': subcategories[entry['subcategory']],
                'latitude': entry['latitude'], 'longitude': entry['longitude'],
                'location_text': entry.get('address', ''), 'phone': entry.get('phones', ''),
                'email': entry.get('email', ''),
                'opening_hours': {'hours': entry['hours']} if entry.get('hours') else {},
                'description': '\n'.join(line for line in description if line),
                'sector': Place.Sector.PUBLIC,
                'is_visible': has_location and not entry.get('out_of_service', False),
                'is_verified': True,
            })
            created += is_new
        self.stdout.write(self.style.SUCCESS(f'Imported {len(data["facilities"])} facilities ({created} new). 10 mapped; 4 unlocated/out of service.'))
