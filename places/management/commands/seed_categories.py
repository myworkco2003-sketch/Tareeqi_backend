import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from places.models import Category, SubCategory


class Command(BaseCommand):
    help = 'Seed categories and subcategories from places/data/categories.json without duplicates.'

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(__file__).resolve().parents[2] / 'data' / 'categories.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        categories_created = subcategories_created = subcategory_count = 0
        for entry in data:
            category, created = Category.objects.update_or_create(
                slug=entry['slug'],
                defaults={
                    'name_ar': entry['name_ar'],
                    'name_en': entry['name_en'],
                    'icon': entry['icon'],
                    'sort_order': entry['sort_order'],
                    'is_active': True,
                },
            )
            categories_created += created
            for sub in entry['subcategories']:
                _, created = SubCategory.objects.update_or_create(
                    category=category,
                    slug=sub['slug'],
                    defaults={
                        'name_ar': sub['name_ar'],
                        'name_en': sub['name_en'],
                    },
                )
                subcategories_created += created
                subcategory_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(data)} categories ({categories_created} new) and '
            f'{subcategory_count} subcategories ({subcategories_created} new).'
        ))
