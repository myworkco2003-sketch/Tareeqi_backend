from django.db import migrations


def create_religious_category_and_reclassify(apps, schema_editor):
    Category = apps.get_model('places', 'Category')
    PlaceSubCategory = apps.get_model('places', 'PlaceSubCategory')
    Place = apps.get_model('places', 'Place')

    # 1. تحديث ترتيب عرض التصنيفات الحالية لإفساح المجال للتصنيف الديني
    Category.objects.filter(slug='tourism').update(sort_order=5)
    Category.objects.filter(slug='transportation').update(sort_order=6)
    Category.objects.filter(slug='public-services').update(sort_order=7)
    Category.objects.filter(slug='security').update(sort_order=8)
    Category.objects.filter(slug='economy').update(sort_order=9)

    # 2. إنشاء تصنيف "دور العبادة والمقدسات" كطبقة رئيسية مستقلة ذات سيادة
    rel_cat, _ = Category.objects.get_or_create(
        slug='religious',
        defaults={
            'name_ar': 'دور العبادة والمقدسات',
            'name_en': 'Places of Worship & Holy Sites',
            'icon': 'moon',
            'color': '#0d9488',
            'sort_order': 4,
            'is_active': True,
        }
    )

    # 3. إنشاء التصنيفات الفرعية المستقلة
    sub_mosque, _ = PlaceSubCategory.objects.get_or_create(
        category=rel_cat,
        slug='mosque',
        defaults={
            'name_ar': 'جوامع ومساجد',
            'name_en': 'Mosques & Masjids',
            'icon': 'moon',
            'color': '#0d9488',
        }
    )
    sub_church, _ = PlaceSubCategory.objects.get_or_create(
        category=rel_cat,
        slug='church',
        defaults={
            'name_ar': 'كنائس وأديرة',
            'name_en': 'Churches & Monasteries',
            'icon': 'church',
            'color': '#0284c7',
        }
    )
    sub_shrine, _ = PlaceSubCategory.objects.get_or_create(
        category=rel_cat,
        slug='shrine',
        defaults={
            'name_ar': 'مقامات ومزارات شريفة',
            'name_en': 'Shrines & Holy Sanctuaries',
            'icon': 'sparkles',
            'color': '#d97706',
        }
    )
    sub_synagogue, _ = PlaceSubCategory.objects.get_or_create(
        category=rel_cat,
        slug='synagogue',
        defaults={
            'name_ar': 'معابد تاريخية',
            'name_en': 'Historic Synagogues & Temples',
            'icon': 'landmark',
            'color': '#b45309',
        }
    )

    # 4. إعادة تصنيف المقامات والمزارات الشريفة
    shrine_ids = [14327, 14503, 14509, 14510, 14512, 14513, 14514, 14515, 14511, 13127]
    Place.objects.filter(id__in=shrine_ids).update(sub_category=sub_shrine)

    # 5. إعادة تصنيف المعابد التاريخية
    Place.objects.filter(id__in=[14352, 14353]).update(sub_category=sub_synagogue)

    # 6. تصحيح المسجد المصنف خطأ كصيدلية
    Place.objects.filter(id=12806).update(sub_category=sub_mosque, description='مكان عبادة - مسجد')

    # 7. نقل كافة المساجد التاريخية المتبقية من السياحة إلى تصنيف الجوامع والمساجد
    Place.objects.filter(sub_category__slug='historic-mosque').update(sub_category=sub_mosque)

    # 8. نقل كافة الكنائس والأديرة من السياحة إلى تصنيف الكنائس والأديرة
    Place.objects.filter(sub_category__slug='historic-church').update(sub_category=sub_church)

    # 9. حذف التصنيفات الفرعية القديمة التابعة للسياحة
    PlaceSubCategory.objects.filter(slug__in=['historic-mosque', 'historic-church']).delete()


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('places', '0005_adminarea_search_text_Bus_search_text_and_more'),
    ]

    operations = [
        migrations.RunPython(create_religious_category_and_reclassify, reverse_func),
    ]
