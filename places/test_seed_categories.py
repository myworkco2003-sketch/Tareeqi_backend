from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from .models import Category, Place, SubCategory


class SeedCategoriesTests(TestCase):
    def seed(self):
        call_command('seed_categories', stdout=StringIO())

    def test_source_hierarchy_and_combined_labels(self):
        self.seed()
        self.assertEqual(Category.objects.count(), 8)
        self.assertEqual(SubCategory.objects.count(), 36)
        self.assertEqual(list(Category.objects.values_list('slug', flat=True)), [
            'damascus-governorate', 'government', 'economy', 'public-facilities',
            'communications', 'education', 'religious', 'healthcare',
        ])
        self.assertEqual(SubCategory.objects.get(category__slug='education', slug='schools').name_ar,
                         'مدارس أساسي')
        self.assertEqual(SubCategory.objects.get(category__slug='education', slug='middle-schools').name_ar,
                         'مدارس إعدادي')
        self.assertEqual(SubCategory.objects.get(category__slug='education', slug='high-schools').name_ar,
                         'مدارس ثانوي')
        self.assertEqual(SubCategory.objects.get(category__slug='healthcare', slug='hospitals').name_ar,
                         'مستشفيات')
        self.assertEqual(SubCategory.objects.filter(category__slug='public-facilities').count(), 15)

    def test_rerun_updates_labels_without_duplicates_or_lost_links(self):
        self.seed()
        sub = SubCategory.objects.get(category__slug='healthcare', slug='hospitals')
        place = Place.objects.create(title_ar='Test', sub_category=sub, latitude=33.51, longitude=36.29)
        sub.name_ar = 'Changed label'
        sub.save()
        extra = Category.objects.create(slug='custom', name_ar='Custom')
        self.seed()
        sub.refresh_from_db()
        place.refresh_from_db()
        self.assertEqual(sub.name_ar, 'مستشفيات')
        self.assertEqual(place.sub_category_id, sub.pk)
        self.assertTrue(Category.objects.filter(pk=extra.pk).exists())
        self.assertEqual(Category.objects.count(), 9)
        self.assertEqual(SubCategory.objects.count(), 36)
