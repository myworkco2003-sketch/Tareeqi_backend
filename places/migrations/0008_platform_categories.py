from django.db import migrations


def ensure_platform_categories(apps, schema_editor):
    Category = apps.get_model('places', 'Category')
    categories = [
        ('culture', 'ثقافي', 'Culture', 'landmark'),
        ('healthcare', 'صحي', 'Healthcare', 'hospital'),
        ('security', 'أمن', 'Security', 'shield'),
        ('government', 'مباني حكومية', 'Government Buildings', 'landmark'),
        ('economy', 'اقتصادي', 'Economy', 'coins'),
        ('public-facilities', 'مرافق عامة', 'Public Facilities', 'trees'),
        ('tourism', 'سياحي', 'Tourism', 'sparkles'),
        ('public-services', 'خدمات', 'Services', 'wrench'),
    ]
    for index, (slug, name_ar, name_en, icon) in enumerate(categories):
        Category.objects.using(schema_editor.connection.alias).update_or_create(
            slug=slug,
            defaults=dict(name_ar=name_ar, name_en=name_en, icon=icon,
                          is_active=True, sort_order=index - 8),
        )


class Migration(migrations.Migration):
    dependencies = [('places', '0007_backfill_search_text')]
    operations = [migrations.RunPython(ensure_platform_categories, migrations.RunPython.noop)]
