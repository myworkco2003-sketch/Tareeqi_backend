from django.db import migrations
from places.text_utils import build_search_index_text


def backfill_all_search_text(apps, schema_editor):
    Place = apps.get_model('places', 'Place')
    AdminArea = apps.get_model('places', 'AdminArea')
    Street = apps.get_model('places', 'Street')
    Bus = apps.get_model('places', 'Bus')

    # 1. Backfill Places
    places = Place.objects.select_related('admin_area', 'sub_category').all()
    batch = []
    for p in places:
        admin_name = p.admin_area.name_ar if p.admin_area else ""
        cat_name = p.sub_category.name_ar if p.sub_category else ""
        p.search_text = build_search_index_text(
            p.title, p.title_en, admin_name, cat_name, p.location_text
        )
        batch.append(p)
        if len(batch) >= 500:
            Place.objects.bulk_update(batch, ['search_text'])
            batch = []
    if batch:
        Place.objects.bulk_update(batch, ['search_text'])

    # 2. Backfill AdminAreas
    for a in AdminArea.objects.select_related('parent').all():
        parent_name = a.parent.name_ar if a.parent else ""
        a.search_text = build_search_index_text(a.name_ar, a.name_en, parent_name)
        a.save(update_fields=['search_text'])

    # 3. Backfill Streets
    for s in Street.objects.select_related('admin_area').all():
        admin_name = s.admin_area.name_ar if s.admin_area else ""
        s.search_text = build_search_index_text(s.name_ar, s.name_en, admin_name)
        s.save(update_fields=['search_text'])

    # 4. Backfill Buss
    for b in Bus.objects.all():
        b.search_text = build_search_index_text(b.name, b.name_en, b.code)
        b.save(update_fields=['search_text'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('places', '0006_create_religious_category'),
    ]

    operations = [
        migrations.RunPython(backfill_all_search_text, reverse_code=noop),
    ]
