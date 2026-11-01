from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Category, SubCategory, AdminArea, Place


class PlacesManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user('place-manager', password='test-only', is_staff=True)
        cls.regular = get_user_model().objects.create_user('reader', password='test-only')
        cls.category = Category.objects.create(name_ar='الصحة', slug='health')
        cls.sub = SubCategory.objects.create(category=cls.category, name_ar='مشفى', slug='hospital')
        cls.other = SubCategory.objects.create(category=Category.objects.create(name_ar='التعليم', slug='education'), name_ar='مدرسة', slug='school')
        cls.area = AdminArea.objects.create(name_ar='المزة', code='test', level=10, boundary={})

    def setUp(self):
        self.client = APIClient()
        self.client.force_login(self.staff)
        self.payload = {'title_ar': 'مشفى اختبار', 'sub_category_id': self.sub.id, 'admin_area_id': self.area.id, 'latitude': 33.51, 'longitude': 36.29, 'communication_info': [{'type': 'phone', 'value': '0111234567'}], 'media': [{'file_url': 'https://example.org/photo.jpg', 'media_type': 'image'}], 'opening_hours': {'السبت': '09:00–17:00'}}

    def create(self, **overrides):
        response = self.client.post('/api/admin/places/', {**self.payload, **overrides}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def test_metadata_relationships(self):
        data = self.client.get('/api/admin/places/metadata/').data
        category = next(c for c in data['categories'] if c['id'] == self.category.id)
        self.assertEqual(category['subcategories'], [{'id': self.sub.id, 'name_ar': 'مشفى'}])
        self.assertIn({'id': self.area.id, 'name_ar': 'المزة'}, data['admin_areas'])
        self.assertTrue(data['csrf_token'])

    def test_create_persist_and_public_coordinates(self):
        pk = self.create()
        place = Place.objects.get(pk=pk)
        self.assertFalse(place.is_verified)
        self.assertTrue(place.search_text)
        self.assertTrue(place.created_at)
        self.assertEqual(place.communication_info.count(), 1)
        self.assertEqual(place.media.count(), 1)
        data = self.client.get(f'/api/places/geojson/?category_id={self.category.id}').json()
        self.assertEqual(data['features'][0]['geometry']['coordinates'], [36.29, 33.51])
        self.assertEqual(data['features'][0]['id'], pk)

    def test_filters_and_pagination(self):
        pk = self.create()
        self.create(title_ar='مدرسة', sub_category_id=self.other.id, is_visible=False)
        query = f'category_id={self.category.id}&admin_area_id={self.area.id}&search=مشفى&is_verified=false&is_visible=true&page_size=1'
        result = self.client.get('/api/admin/places/?' + query).data
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['results'][0]['id'], pk)
        result = self.client.get('/api/admin/places/?page_size=1').data
        self.assertEqual(result['count'], 2)
        self.assertIsNotNone(result['next'])

    def test_long_search_text_fits_existing_column(self):
        pk = self.create(title_ar='أ' * 255, title_en='b' * 255, location_text='c' * 255)
        self.assertLessEqual(len(Place.objects.get(pk=pk).search_text), 600)

    def test_update_hide_delete(self):
        pk = self.create()
        response = self.client.patch(f'/api/admin/places/{pk}/', {'longitude': 36.3, 'title_ar': 'اسم جديد', 'is_visible': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Place.objects.get(pk=pk).longitude, 36.3)
        self.assertEqual(self.client.get('/api/places/geojson/').json()['features'], [])
        self.assertEqual(self.client.get(f'/api/places/{pk}/').status_code, 404)
        self.assertEqual(Place.objects.get(pk=pk).communication_info.count(), 1)
        self.assertEqual(self.client.delete(f'/api/admin/places/{pk}/').status_code, 204)
        self.assertFalse(Place.objects.filter(pk=pk).exists())

    def test_invalid_payloads_do_not_write(self):
        for invalid in ({'latitude': 91}, {'longitude': 181}, {'latitude': 0}, {'sub_category_id': 999999}, {'title_ar': ''}, {'opening_hours': []}, {'media': [{'file_url': 'javascript:alert(1)'}]}):
            response = self.client.post('/api/admin/places/', {**self.payload, **invalid}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Place.objects.count(), 0)

    def test_bbox_and_invalid_query(self):
        self.create()
        response = self.client.get('/api/admin/places/geojson/?bbox=36.2,33.5,36.4,33.6')
        self.assertEqual(len(response.data['features']), 1)
        self.assertEqual(self.client.get('/api/admin/places/geojson/?bbox=0,0,1,1').data['features'], [])
        for query in ('bbox=nan,0,1,1', 'bbox=2,2,1,1', 'category_id=abc', 'is_visible=yes', 'page_size=zero', 'page_size=-1'):
            self.assertEqual(self.client.get('/api/admin/places/?' + query).status_code, 400)
        self.assertEqual(self.client.get('/api/places/geojson/?bbox=broken').status_code, 400)

    def test_staff_permission_required(self):
        for user in (None, self.regular):
            self.client.logout()
            if user:
                self.client.force_login(user)
            self.assertEqual(self.client.get('/api/admin/places/').status_code, 403)
            self.assertEqual(self.client.post('/api/admin/places/', self.payload, format='json').status_code, 403)

    def test_csrf_required_for_session_writes(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(client.post('/api/admin/places/', self.payload, format='json').status_code, 403)
        token = client.get('/api/admin/places/metadata/').data['csrf_token']
        self.assertEqual(client.post('/api/admin/places/', self.payload, format='json', HTTP_X_CSRFTOKEN=token).status_code, 201)
