from io import StringIO
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import Category, SubCategory, Place


@override_settings(PLACES_SUBMISSION_AUTO_PUBLISH=False, PLACES_FORM_LINK_VERSION='test', PLACES_FORM_LINK_MAX_AGE=3600)
class SubmissionTests(TestCase):
    def setUp(self):
        cache.clear()
        category = Category.objects.create(name_ar='الصحة', slug='health')
        sub = SubCategory.objects.create(category=category, name_ar='عيادة', slug='clinic')
        self.payload = {'title_ar': 'عيادة جديدة', 'sub_category_id': sub.pk, 'latitude': 33.51, 'longitude': 36.29, 'is_visible': True, 'is_verified': True}
        self.client = APIClient(enforce_csrf_checks=True)

    def test_link_creates_without_login_and_cannot_self_publish_or_verify(self):
        response = self.client.post('/api/place-submissions/', self.payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        place = Place.objects.get(pk=response.data['id'])
        self.assertFalse(place.is_verified)
        self.assertFalse(place.is_visible)
        self.assertEqual(self.client.get('/api/places/geojson/').json()['count'], 0)

    @override_settings(PLACES_SUBMISSION_AUTO_PUBLISH=True)
    def test_owner_can_enable_immediate_publication(self):
        response = self.client.post('/api/place-submissions/', self.payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['is_visible'])
        self.assertFalse(response.data['is_verified'])
        self.assertEqual(self.client.get('/api/places/geojson/').json()['count'], 1)

    def test_invitation_does_not_grant_management_or_list_access(self):
        self.assertEqual(self.client.get('/api/place-submissions/').status_code, 405)
        self.assertEqual(self.client.get('/api/admin/places/').status_code, 403)
        self.assertEqual(self.client.post('/api/admin/places/', self.payload, format='json').status_code, 403)
        self.assertEqual(self.client.patch('/api/admin/places/1/', {}, format='json').status_code, 403)
        self.assertEqual(self.client.delete('/api/admin/places/1/').status_code, 403)

    def test_metadata_without_session(self):
        response = self.client.get('/api/place-submissions/metadata/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['auto_publish'])
        self.assertEqual(len(response.data['categories'][0]['subcategories']), 1)

    def test_submission_rate_limit_is_per_client(self):
        from .submission_api import SubmissionThrottle
        from unittest.mock import patch
        with patch.object(SubmissionThrottle, 'rate', '1/hour'):
            self.assertEqual(self.client.post('/api/place-submissions/', self.payload, format='json').status_code, 201)
            self.assertEqual(self.client.post('/api/place-submissions/', self.payload, format='json').status_code, 429)
        self.assertEqual(Place.objects.count(), 1)

    def test_invalid_coordinates_do_not_write(self):
        response = self.client.post('/api/place-submissions/', {**self.payload, 'latitude': 0}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Place.objects.count(), 0)

    def test_command_creates_working_fragment_link(self):
        output = StringIO()
        call_command('create_place_form_link', base_url='https://dashboard.example.com', stdout=output)
        link = output.getvalue().strip()
        self.assertTrue(link.startswith('https://dashboard.example.com/places/new#token='))
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + link.split('#token=')[1])
        self.assertEqual(self.client.get('/api/place-submissions/metadata/').status_code, 200)
