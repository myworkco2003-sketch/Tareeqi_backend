from types import SimpleNamespace
from unittest.mock import patch
import json

from django.test import RequestFactory, SimpleTestCase

from .views import list_streets_geojson


class StreetMapDataTests(SimpleTestCase):
    def test_database_geometry_names_and_road_classes(self):
        geometry = {'type': 'LineString', 'coordinates': [[36.29, 33.51], [36.30, 33.52]]}
        streets = [
            SimpleNamespace(id=i, name_ar='شارع تجريبي', name_en='Test Street',
                            highway_type=highway, admin_area_id=7, geometry=geometry)
            for i, highway in enumerate(['residential', 'primary_link', 'footway'], start=1)
        ]
        with patch('places.views.Street.objects.filter') as query:
            query.return_value.iterator.return_value = iter(streets)
            response = list_streets_geojson(RequestFactory().get('/api/streets/geojson/'))
            query.assert_called_once_with(is_active=True)
        data = json.loads(response.content)
        self.assertEqual(data['count'], 3)
        self.assertEqual([f['properties']['class'] for f in data['features']], ['minor', 'primary', 'path'])
        self.assertEqual(data['features'][1]['properties']['ramp'], 1)
        self.assertEqual(data['features'][0]['geometry'], geometry)
        self.assertEqual(data['features'][0]['properties']['name:ar'], 'شارع تجريبي')

    def test_empty_database_returns_empty_collection(self):
        with patch('places.views.Street.objects.filter') as query:
            query.return_value.iterator.return_value = iter([])
            response = list_streets_geojson(RequestFactory().get('/api/streets/geojson/'))
        self.assertEqual(json.loads(response.content), {
            'type': 'FeatureCollection', 'count': 0, 'features': [],
        })
