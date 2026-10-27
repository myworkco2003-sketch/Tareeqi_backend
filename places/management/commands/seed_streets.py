import json
from pathlib import Path
from django.core.management.base import BaseCommand
from places.models import AdminArea, Street


class Command(BaseCommand):
    help = "Import Damascus streets from GeoJSON dataset"

    def handle(self, *args, **options):
        geojson_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "damascus_streets.geojson"
        
        if not geojson_path.exists():
            self.stderr.write(self.style.ERROR(f"GeoJSON file not found: {geojson_path}"))
            return

        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", [])
        self.stdout.write(f"Found {len(features)} street features. Importing into database...")

        # Cache admin areas by name_ar for fast lookup
        admin_map = {}
        for a in AdminArea.objects.all():
            admin_map[a.name_ar.strip()] = a
            # Also store without "حي " prefix for flexible matching
            if a.name_ar.startswith("حي "):
                admin_map[a.name_ar[3:].strip()] = a

        imported_count = 0
        for feat in features:
            props = feat.get("properties", {})
            name_ar = (props.get("name_ar") or "").strip()
            if not name_ar:
                continue

            name_en = (props.get("name_en") or "").strip()
            highway_type = (props.get("highway_type") or "residential").strip()
            center = props.get("center") or [36.295, 33.513]
            bbox = props.get("bbox") or [center[0], center[1], center[0], center[1]]
            geometry = feat.get("geometry") or {}

            # Match admin area
            neigh_name = (props.get("neighborhood") or "").strip()
            admin_area = admin_map.get(neigh_name)
            if not admin_area and neigh_name.startswith("حي "):
                admin_area = admin_map.get(neigh_name[3:].strip())

            Street.objects.update_or_create(
                id=props.get("id"),
                defaults={
                    "name_ar": name_ar,
                    "name_en": name_en,
                    "highway_type": highway_type,
                    "admin_area": admin_area,
                    "center_lon": center[0],
                    "center_lat": center[1],
                    "bbox": bbox,
                    "geometry": geometry,
                    "is_active": True,
                }
            )
            imported_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully imported {imported_count} streets into database."))
        self.stdout.write(self.style.SUCCESS(f"Total streets in database: {Street.objects.count()}"))
