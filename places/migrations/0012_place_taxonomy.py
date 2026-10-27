from django.db import migrations


CATEGORIES = {
    'damascus-governorate': {
        'name_ar': 'مباني محافظة دمشق',
        'name_en': 'Damascus Governorate Buildings',
        'icon': 'landmark',
        'color': '#064239',
        'sort_order': 0,
    },
    'government': {
        'name_ar': 'مباني حكومية',
        'name_en': 'Government Buildings',
        'icon': 'landmark',
        'color': '#1d3557',
        'sort_order': 1,
    },
    'economy': {
        'name_ar': 'اقتصاد',
        'name_en': 'Economy',
        'icon': 'coins',
        'color': '#b45309',
        'sort_order': 2,
    },
    'public-facilities': {
        'name_ar': 'المرافق العامة',
        'name_en': 'Public Facilities',
        'icon': 'trees',
        'color': '#2d6a4f',
        'sort_order': 3,
    },
    'communications': {
        'name_ar': 'اتصالات',
        'name_en': 'Communications',
        'icon': 'phone',
        'color': '#457b9d',
        'sort_order': 4,
    },
    'education': {
        'name_ar': 'تربية وتعليم',
        'name_en': 'Education',
        'icon': 'graduation-cap',
        'color': '#1d3557',
        'sort_order': 5,
    },
    'religious': {
        'name_ar': 'دور العبادة',
        'name_en': 'Places of Worship',
        'icon': 'moon',
        'color': '#0d9488',
        'sort_order': 6,
    },
    'healthcare': {
        'name_ar': 'صحة',
        'name_en': 'Healthcare',
        'icon': 'hospital',
        'color': '#e63946',
        'sort_order': 7,
    },
}

SUBCATEGORIES = {
    'damascus-governorate': [
        ('citizen-service-centers', 'مراكز خدمة المواطن', 'Citizen Service Centers', 'building-2', False),
        ('municipal-service-buildings', 'مباني البلديات (دوائر الخدمات)', 'Municipal Service Buildings', 'landmark', False),
        ('municipalities', 'بلديات', 'Municipalities', 'landmark', False),
    ],
    'government': [
        ('ministries', 'الوزارات', 'Ministries', 'landmark', False),
        ('central-directorates', 'المديريات المركزية', 'Central Directorates', 'building-2', False),
        ('embassies-consulates', 'السفارات والقنصليات', 'Embassies and Consulates', 'building-2', False),
        ('courts', 'المحاكم', 'Courts', 'landmark', False),
        ('police-stations', 'مخافر', 'Police Stations', 'shield', False),
    ],
    'economy': [
        ('public-banks', 'بنوك عامة', 'Public Banks', 'landmark', False),
        ('private-banks', 'بنوك خاصة', 'Private Banks', 'landmark', True),
        ('atms', 'ATM', 'ATMs', 'coins', False),
    ],
    'public-facilities': [
        ('parks', 'حدائق', 'Parks', 'trees', False),
        ('squares', 'ساحات', 'Squares', 'landmark', False),
        ('transit-terminals', 'مراكز انطلاق', 'Transit Terminals', 'bus', False),
        ('interchange-center', 'مركز تبادلي', 'Interchange Center', 'bus', False),
        ('airports', 'مطارات', 'Airports', 'plane', False),
        ('archaeological-landmarks', 'معالم أثرية', 'Archaeological Landmarks', 'landmark', False),
    ],
    'communications': [
        ('post-offices', 'مراكز بريد', 'Post Offices', 'mail', False),
        ('mobile-service-centers', 'مراكز خدمة الجوال', 'Mobile Service Centers', 'phone', False),
    ],
    'education': [
        ('public-basic-schools', 'مدارس عامة - أساسي', 'Public Basic Schools', 'graduation-cap', False),
        ('public-preparatory-schools', 'مدارس عامة - إعدادي', 'Public Preparatory Schools', 'graduation-cap', False),
        ('public-secondary-schools', 'مدارس عامة - ثانوي', 'Public Secondary Schools', 'graduation-cap', False),
        ('private-basic-schools', 'مدارس خاصة - أساسي', 'Private Basic Schools', 'graduation-cap', True),
        ('private-preparatory-schools', 'مدارس خاصة - إعدادي', 'Private Preparatory Schools', 'graduation-cap', True),
        ('private-secondary-schools', 'مدارس خاصة - ثانوي', 'Private Secondary Schools', 'graduation-cap', True),
        ('colleges', 'كليات', 'Colleges', 'graduation-cap', False),
    ],
    'religious': [
        ('mosques', 'مساجد', 'Mosques', 'moon', False),
        ('churches', 'كنائس', 'Churches', 'church', False),
        ('sharia-centers', 'مراكز شرعية', 'Sharia Centers', 'landmark', False),
    ],
    'healthcare': [
        ('public-hospitals', 'مستشفيات عامة', 'Public Hospitals', 'hospital', False),
        ('private-hospitals', 'مستشفيات خاصة', 'Private Hospitals', 'hospital', True),
        ('blood-banks', 'بنوك الدم', 'Blood Banks', 'droplets', False),
        ('health-centers', 'مراكز صحية', 'Health Centers', 'hospital', False),
        ('pharmacies', 'صيدليات', 'Pharmacies', 'pill', False),
    ],
}


def create_place_taxonomy(apps, schema_editor):
    Category = apps.get_model('places', 'Category')
    SubCategory = apps.get_model('places', 'PlaceSubCategory')
    alias = schema_editor.connection.alias

    # Preserve existing place links while adopting the requested plural slugs.
    religious = Category.objects.using(alias).filter(slug='religious').first()
    if religious:
        for old_slug, new_slug in [('mosque', 'mosques'), ('church', 'churches')]:
            old_subcategory = SubCategory.objects.using(alias).filter(
                category=religious,
                slug=old_slug,
            ).first()
            if old_subcategory and not SubCategory.objects.using(alias).filter(
                category=religious,
                slug=new_slug,
            ).exists():
                old_subcategory.slug = new_slug
                old_subcategory.save(using=alias, update_fields=['slug'])

    categories = {}
    for slug, defaults in CATEGORIES.items():
        category, _ = Category.objects.using(alias).update_or_create(
            slug=slug,
            defaults={**defaults, 'is_active': True},
        )
        categories[slug] = category

    for category_slug, subcategories in SUBCATEGORIES.items():
        category = categories[category_slug]
        for slug, name_ar, name_en, icon, is_private in subcategories:
            SubCategory.objects.using(alias).update_or_create(
                category=category,
                slug=slug,
                defaults={
                    'name_ar': name_ar,
                    'name_en': name_en,
                    'icon': icon,
                    'is_private': is_private,
                },
            )


def reverse_place_taxonomy(apps, schema_editor):
    Category = apps.get_model('places', 'Category')
    SubCategory = apps.get_model('places', 'PlaceSubCategory')
    alias = schema_editor.connection.alias

    for category_slug, subcategories in SUBCATEGORIES.items():
        category = Category.objects.using(alias).filter(slug=category_slug).first()
        if category:
            SubCategory.objects.using(alias).filter(
                category=category,
                slug__in=[item[0] for item in subcategories],
            ).delete()

    Category.objects.using(alias).filter(slug='damascus-governorate').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('places', '0011_alter_adminarea_search_text'),
    ]

    operations = [
        migrations.RunPython(create_place_taxonomy, reverse_place_taxonomy),
    ]
