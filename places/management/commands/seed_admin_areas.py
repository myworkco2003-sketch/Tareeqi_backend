import json
from pathlib import Path
from django.core.management.base import BaseCommand
from places.models import AdminArea


class Command(BaseCommand):
    help = "Import Damascus administrative areas (municipalities and neighborhoods) from GeoJSON"

    def handle(self, *args, **options):
        geojson_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "damascus_admin_areas.geojson"
        
        if not geojson_path.exists():
            self.stderr.write(self.style.ERROR(f"GeoJSON file not found: {geojson_path}"))
            return

        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", [])
        self.stdout.write(f"Found {len(features)} features in GeoJSON. Beginning import...")

        # 1. المرحلة الأولى: استيراد البلديات (Level 9)
        mun_map = {}
        for feat in features:
            props = feat.get("properties", {})
            if props.get("level") == 9:
                obj, created = AdminArea.objects.update_or_create(
                    id=props.get("id"),
                    defaults={
                        "code": props.get("code") or "",
                        "pcode": props.get("pcode"),
                        "level": 9,
                        "name_ar": props.get("name_ar") or "",
                        "name_en": props.get("name_en") or "",
                        "boundary": feat.get("geometry"),
                    }
                )
                mun_map[obj.id] = obj

        self.stdout.write(self.style.SUCCESS(f"Imported {len(mun_map)} municipalities (Level 9)"))

        # 2. المرحلة الثانية: استيراد الأحياء (Level 10) وربطها بالبلديات
        nbh_count = 0
        for feat in features:
            props = feat.get("properties", {})
            if props.get("level") == 10:
                parent_id = props.get("parent_id")
                parent_obj = mun_map.get(parent_id)

                AdminArea.objects.update_or_create(
                    id=props.get("id"),
                    defaults={
                        "code": props.get("code") or "",
                        "pcode": props.get("pcode"),
                        "level": 10,
                        "name_ar": props.get("name_ar") or "",
                        "name_en": props.get("name_en") or "",
                        "parent": parent_obj,
                        "boundary": feat.get("geometry"),
                    }
                )
                nbh_count += 1

        self.stdout.write(self.style.SUCCESS(f"Imported {nbh_count} neighborhoods (Level 10)"))
        self.stdout.write(self.style.SUCCESS(f"Total admin areas stored in database: {AdminArea.objects.count()}"))
