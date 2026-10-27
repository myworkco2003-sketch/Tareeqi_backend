from django.db import migrations


LEGACY_SLUGS = ['shrine', 'synagogue']


def remove_legacy_religious_subcategories(apps, schema_editor):
    Category = apps.get_model('places', 'Category')
    SubCategory = apps.get_model('places', 'PlaceSubCategory')
    alias = schema_editor.connection.alias
    religious = Category.objects.using(alias).filter(slug='religious').first()
    if religious:
        SubCategory.objects.using(alias).filter(
            category=religious,
            slug__in=LEGACY_SLUGS,
        ).delete()


def restore_legacy_religious_subcategories(apps, schema_editor):
    Category = apps.get_model('places', 'Category')
    SubCategory = apps.get_model('places', 'PlaceSubCategory')
    alias = schema_editor.connection.alias
    religious = Category.objects.using(alias).filter(slug='religious').first()
    if not religious:
        return

    values = {
        'shrine': ('مقامات ومزارات شريفة', 'Shrines & Holy Sanctuaries', 'sparkles'),
        'synagogue': ('معابد تاريخية', 'Historic Synagogues & Temples', 'landmark'),
    }
    for slug, (name_ar, name_en, icon) in values.items():
        SubCategory.objects.using(alias).get_or_create(
            category=religious,
            slug=slug,
            defaults={
                'name_ar': name_ar,
                'name_en': name_en,
                'icon': icon,
                'is_private': False,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('places', '0012_place_taxonomy'),
    ]

    operations = [
        migrations.RunPython(
            remove_legacy_religious_subcategories,
            restore_legacy_religious_subcategories,
        ),
    ]
