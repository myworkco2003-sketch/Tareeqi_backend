from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from .models import Bus, BusRoute


class BusSchemaTests(TestCase):
    def setUp(self):
        self.bus = Bus.objects.create(name='Test line', color='#123456', old_price=500, new_price=750)
        self.geometry = {'type': 'LineString', 'coordinates': [[36.28, 33.51], [36.30, 33.52]]}
        self.route = BusRoute.objects.create(
            bus_line=self.bus, geometry=self.geometry, direction='outbound',
            distance=12500, trip_time=35, start_point='Start district', end_point='End district',
        )

    def test_exactly_two_tables_with_requested_columns(self):
        expected = {
            'BUS': {'UniqueID', 'name', 'color', 'oldPrice', 'newPrice', 'isActive'},
            'BUS_ROUTE': {'UniqueID', 'busID', 'version', 'lineString', 'distance', 'tripTime', 'direction', 'startPoint', 'endPoint', 'isActive'},
        }
        tables = connection.introspection.table_names()
        for name in ['places_Bus', 'places_busroute', 'places_busstop', 'places_busstop_routes', 'places_routespecification']:
            self.assertNotIn(name, tables)
        with connection.cursor() as cursor:
            for table, columns in expected.items():
                actual = connection.introspection.get_table_description(cursor, table)
                self.assertEqual({column.name for column in actual}, columns)

    def test_units_and_prices(self):
        self.route.refresh_from_db()
        self.bus.refresh_from_db()
        self.assertEqual(self.route.distance, 12500)
        self.assertEqual(self.route.trip_time, 35)
        self.assertEqual(self.bus.old_price, Decimal('500.00'))
        self.assertEqual(self.bus.new_price, Decimal('750.00'))
        self.assertEqual(self.route.start_point, 'Start district')

    def test_history_and_reactivation_per_direction(self):
        inbound = BusRoute.objects.create(bus_line=self.bus, geometry=self.geometry, direction='inbound')
        replacement = BusRoute.objects.create(bus_line=self.bus, geometry=self.geometry, direction='outbound', version=2, is_active=False)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BusRoute.objects.filter(pk=replacement.pk).update(is_active=True)
        self.route.is_active = False
        self.route.save()
        replacement.is_active = True
        replacement.save()
        replacement.is_active = False
        replacement.save()
        self.route.is_active = True
        self.route.save()
        self.assertEqual(BusRoute.objects.count(), 3)
        inbound.refresh_from_db()
        self.assertTrue(inbound.is_active)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BusRoute.objects.create(bus_line=self.bus, geometry=self.geometry, direction='outbound', version=1, is_active=False)

    def test_existing_endpoints_read_new_tables(self):
        line = self.client.get('/api/transit/lines/').json()['results'][0]
        self.assertEqual(line['cost'], 750)
        self.assertEqual(line['length_km'], 12.5)
        self.assertEqual(line['trip_time_mins'], 35)
        self.assertEqual(line['start_terminal']['name'], 'Start district')
        for path in ['/api/transit/all-routes-geojson/', f'/api/transit/routes/{self.route.id}/', '/api/search/?q=Test']:
            self.assertEqual(self.client.get(path).status_code, 200)

    def test_inactive_line_excluded_from_map(self):
        self.bus.is_active = False
        self.bus.save()
        self.assertEqual(self.client.get('/api/transit/lines/').json()['count'], 0)
        self.assertEqual(self.client.get('/api/transit/all-routes-geojson/').json()['count'], 0)

    def test_both_directions_have_independent_geometry_and_terminals(self):
        return_geometry = {'type': 'LineString', 'coordinates': [[36.30, 33.52], [36.32, 33.53], [36.28, 33.51]]}
        inbound = BusRoute.objects.create(bus_line=self.bus, geometry=return_geometry,
            direction='inbound', start_point='End district', end_point='Start district', trip_time=30)
        routes = self.client.get('/api/transit/lines/').json()['results'][0]['routes']
        self.assertEqual(len(routes), 2)
        self.assertEqual(routes[0]['geometry'], self.geometry)
        self.assertEqual(routes[1]['geometry'], return_geometry)
        self.assertEqual(routes[1]['route_id'], inbound.id)
        self.assertEqual(routes[1]['start_terminal']['name'], 'End district')
        self.assertEqual(routes[1]['stops'][1]['coordinates'], return_geometry['coordinates'][-1])
