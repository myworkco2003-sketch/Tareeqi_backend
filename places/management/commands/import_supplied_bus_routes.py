import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction

from places.models import Bus, BusRoute


class Command(BaseCommand):
    help = 'Import the supplied four routes as two bus lines, with confirmed colours and durations.'

    def add_arguments(self, parser):
        parser.add_argument('--minutes', nargs=4, type=int, required=True, help='Minutes in route ID order: 1, 2, 3, 4; 0 means unspecified.')
        parser.add_argument('--colors', nargs=2, required=True, help='Colours for bus IDs 1 and 2.')

    @transaction.atomic
    def handle(self, *args, **options):
        if any(value < 0 for value in options['minutes']):
            raise CommandError('Durations cannot be negative.')
        if any(not re.fullmatch(r'#[0-9A-Fa-f]{6}', color) for color in options['colors']):
            raise CommandError('Use six-digit hex colours.')
        # Do not overwrite any existing transport records.
        if Bus.objects.exists() or BusRoute.objects.exists():
            raise CommandError('Bus tables must be empty for this initial import.')
        rows = json.loads((Path(__file__).resolve().parents[2] / 'data' / 'imported_bus_routes.json').read_text(encoding='utf-8'))
        if sorted(row['id'] for row in rows) != [1, 2, 3, 4]:
            raise CommandError('Expected route IDs 1 through 4.')
        names = {
            1: ('ضاحية قدسيا - جسر الحرية (غربية)', 'ضاحية قدسيا', 'جسر الحرية'),
            2: ('الدوار الشمالي (مساكن)', 'كراجات العباسيين', 'المزة'),
        }
        for bus_id, (name, _, _) in names.items():
            bus = Bus(id=bus_id, name=name, color=options['colors'][bus_id-1],
                          old_price=None, new_price=50, is_active=True)
            bus.full_clean()
            bus.save(force_insert=True)
        for row in rows:
            _, start, end = names[row['bus_id']]
            if row['direction'] == 'inbound':
                start, end = end, start
            route = BusRoute(
                id=row['id'], bus_line_id=row['bus_id'], version=row['version'],
                geometry=row['geometry'], distance=row['distance'],
                trip_time=options['minutes'][row['id']-1], direction=row['direction'],
                start_point=start, end_point=end, is_active=row['is_active'],
            )
            route.full_clean()
            route.save(force_insert=True)
        # Keep automatic IDs valid after explicitly importing the starting IDs.
        with connection.cursor() as cursor:
            for sql in connection.ops.sequence_reset_sql(no_style(), [Bus, BusRoute]):
                cursor.execute(sql)
        self.stdout.write(self.style.SUCCESS('Imported BUS 1–2 and BUS_ROUTE 1–4. Current fare: 50 SYP; previous fare: unknown.'))
