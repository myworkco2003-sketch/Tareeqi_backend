from django.core.management.base import BaseCommand
from places.models import Place, AdminArea, Street, Bus
from places.text_utils import build_search_index_text


class Command(BaseCommand):
    help = "Backfill normalized search_text vector for Place, AdminArea, Street, and Bus"

    def handle(self, *args, **options):
        self.stdout.write("Backfilling search_text vectors...")

        # 1. Backfill Places
        places = Place.objects.select_related('admin_area', 'sub_category').all()
        place_count = 0
        batch = []
        for p in places:
            admin_name = p.admin_area.name_ar if p.admin_area else ""
            cat_name = p.sub_category.name_ar if p.sub_category else ""
            p.search_text = build_search_index_text(
                p.title_ar, p.title_en, admin_name, cat_name, p.location_text
            )
            batch.append(p)
            place_count += 1
            if len(batch) >= 500:
                Place.objects.bulk_update(batch, ['search_text'])
                batch = []
        if batch:
            Place.objects.bulk_update(batch, ['search_text'])
        self.stdout.write(self.style.SUCCESS(f"✓ Backfilled {place_count} Place records."))

        # 2. Backfill AdminAreas
        areas = AdminArea.objects.select_related('parent').all()
        area_count = 0
        for a in areas:
            parent_name = a.parent.name_ar if a.parent else ""
            a.search_text = build_search_index_text(a.name_ar, a.name_en, parent_name)
            a.save(update_fields=['search_text'])
            area_count += 1
        self.stdout.write(self.style.SUCCESS(f"✓ Backfilled {area_count} AdminArea records."))

        # 3. Backfill Streets
        streets = Street.objects.select_related('admin_area').all()
        street_count = 0
        for s in streets:
            admin_name = s.admin_area.name_ar if s.admin_area else ""
            s.search_text = build_search_index_text(s.name_ar, s.name_en, admin_name)
            s.save(update_fields=['search_text'])
            street_count += 1
        self.stdout.write(self.style.SUCCESS(f"✓ Backfilled {street_count} Street records."))

        # 4. Backfill Buss
        lines = Bus.objects.all()
        line_count = 0
        for b in lines:
            b.save()
            line_count += 1
        self.stdout.write(self.style.SUCCESS(f"✓ Backfilled {line_count} Bus records."))

        self.stdout.write(self.style.SUCCESS("All search vectors successfully backfilled!"))
