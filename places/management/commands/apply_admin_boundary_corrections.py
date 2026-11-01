import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from places.models import AdminArea


def geometry_digest(geometry):
    return hashlib.sha256(json.dumps(geometry, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class Command(BaseCommand):
    help = 'Apply reviewed OSM boundary corrections without changing IDs, names or parent relationships.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--backup', type=Path)
        parser.add_argument('--manifest', type=Path, default=Path(settings.BASE_DIR) / 'data/admin_boundary_corrections.json')

    def handle(self, *args, **options):
        manifest = json.loads(options['manifest'].read_text(encoding='utf-8'))
        data = json.loads((Path(settings.BASE_DIR) / 'data/damascus_admin_areas.geojson').read_text(encoding='utf-8'))
        features = {f['properties']['id']: f for f in data['features']}
        changes = manifest['changes']
        if len({change['id'] for change in changes}) != len(changes):
            raise CommandError('Duplicate IDs in correction manifest.')
        backup = options['backup']
        if not options['dry_run'] and backup is None:
            raise CommandError('--backup is required when applying corrections.')

        with transaction.atomic():
            areas = {area.id: area for area in AdminArea.objects.select_for_update().filter(id__in=[c['id'] for c in changes])}
            pending = []
            before = []
            for change in changes:
                area = areas.get(change['id'])
                if area is None or area.id not in features:
                    raise CommandError(f"Missing area {change['id']}.")
                feature = features[area.id]
                props = feature['properties']
                if (area.name_ar, area.level, area.parent_id) != (change['name_ar'], change['level'], change['parent_id']):
                    raise CommandError(f'Area {area.id} identity changed since review; aborting.')
                if (props['name_ar'], props['level']) != (area.name_ar, area.level):
                    raise CommandError(f'Area {area.id} source identity mismatch.')
                geometry = feature['geometry']
                if geometry_digest(geometry) != change['after_sha256']:
                    raise CommandError(f'Area {area.id} source geometry changed since review.')
                if area.boundary == geometry:
                    continue
                if geometry_digest(area.boundary) != change['before_sha256']:
                    raise CommandError(f'Area {area.id} was independently edited; aborting without overwriting it.')
                before.append({'id': area.id, 'name_ar': area.name_ar, 'level': area.level,
                               'parent_id': area.parent_id, 'boundary': area.boundary})
                area.boundary = geometry
                pending.append(area)
            if not options['dry_run'] and pending:
                backup.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with backup.open('x', encoding='utf-8') as output:
                        json.dump({'source': str(options['manifest']), 'areas': before}, output, ensure_ascii=False, indent=2)
                except FileExistsError as exc:
                    raise CommandError('Backup exists; use a new path to avoid overwriting the original backup.') from exc
                AdminArea.objects.bulk_update(pending, ['boundary'])
        action = 'Would update' if options['dry_run'] else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{action} {len(pending)} boundaries; identities and relationships unchanged.'))
