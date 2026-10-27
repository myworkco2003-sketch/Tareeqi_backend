from django.test import TestCase, Client
from django.urls import reverse
from places.models import AdminArea, Street, Category, PlaceSubCategory, Place


class DamascusPlacesModelAndApiTests(TestCase):
    def setUp(self):
        self.client = Client(headers={'host': 'localhost'})

        # 1. إنشاء تقسيم إداري تجريبي
        self.municipality = AdminArea.objects.create(
            name_ar="بلدية المزة",
            name_en="Mezzeh Municipality",
            code="MZ01",
            level=9,
            boundary={"type": "Polygon", "coordinates": [[[36.25, 33.50], [36.26, 33.50], [36.26, 33.51], [36.25, 33.51], [36.25, 33.50]]]}
        )
        self.neighborhood = AdminArea.objects.create(
            name_ar="المزة فيلات شرقية",
            name_en="Mezzeh Eastern Villas",
            code="MZ01-10",
            level=10,
            parent=self.municipality,
            boundary={"type": "Polygon", "coordinates": [[[36.255, 33.502], [36.258, 33.502], [36.258, 33.508], [36.255, 33.508], [36.255, 33.502]]]}
        )

        # 2. إنشاء تصنيف وتصنيف فرعي
        self.category = Category.objects.create(
            name_ar="القطاع الصحي والمشافي",
            name_en="Healthcare",
            slug="healthcare",
            icon="hospital",
            color="#e63946",
            is_active=True,
            sort_order=1
        )
        self.sub_category = PlaceSubCategory.objects.create(
            category=self.category,
            name_ar="مشفى حكومي",
            name_en="Public Hospital",
            slug="public-hospital",
            is_private=False
        )

        # 3. إنشاء منشأة تجريبية (Place) بكافة حقول الاتصال الجديدة والقطاع
        self.place = Place.objects.create(
            title="مشفى المواساة الجامعي",
            title_en="Al-Mouwasat University Hospital",
            description="مشفى تعليمي حكومي رائد في دمشق",
            sub_category=self.sub_category,
            admin_area=self.neighborhood,
            sector=Place.Sector.PUBLIC,
            latitude=33.5123,
            longitude=36.2712,
            location_text="دمشق - المزة",
            phone="011-2133000",
            mobile="0991000000",
            short_number="115",
            whatsapp="963991000000",
            email="info@mouwasat-hospital.sy",
            website="https://mouwasat-hospital.sy",
            social_media={"facebook": "https://facebook.com/mouwasat"},
            is_verified=True,
            is_visible=True
        )

        # 4. إنشاء شارع تجريبي (Street)
        self.street = Street.objects.create(
            name_ar="شارع فايز منصور",
            name_en="Fayez Mansour Street",
            highway_type="primary",
            admin_area=self.neighborhood,
            center_lat=33.5120,
            center_lon=36.2710,
            bbox=[36.265, 33.508, 36.275, 33.515],
            geometry={"type": "LineString", "coordinates": [[36.265, 33.508], [36.275, 33.515]]},
            is_active=True
        )

    def test_admin_area_creation_and_str(self):
        """فحص نص وتمثيل المناطق الإدارية"""
        self.assertEqual(str(self.municipality), "بلدية: بلدية المزة (MZ01)")
        self.assertEqual(str(self.neighborhood), "حي: المزة فيلات شرقية (MZ01-10)")
        self.assertEqual(self.neighborhood.parent.name_ar, "بلدية المزة")

    def test_place_category_property_backward_compatibility(self):
        """فحص أن خاصية p.category تعمل ديناميكياً بدقة دون وجود عمود مباشر"""
        p = Place.objects.select_related('sub_category__category').get(id=self.place.id)
        self.assertIsNotNone(p.category)
        self.assertEqual(p.category.slug, "healthcare")
        self.assertEqual(p.category.name_ar, "القطاع الصحي والمشافي")

    def test_effective_icon_and_color_fallback(self):
        """فحص أن التصنيف الفرعي يرث الأيقونة واللون تلقائياً إذا لم يُحددا"""
        sub = self.sub_category
        self.assertEqual(sub.effective_icon, "hospital")
        self.assertEqual(sub.effective_color, "#e63946")

        # عند تحديد أيقونة مخصصة للتصنيف الفرعي
        sub.icon = "cross"
        sub.color = "#00ff00"
        sub.save()
        self.assertEqual(sub.effective_icon, "cross")
        self.assertEqual(sub.effective_color, "#00ff00")

    def test_category_places_property(self):
        """فحص أن خاصية category.places تُرجع الأماكن بدقة"""
        places_count = self.category.places.filter(is_visible=True).count()
        self.assertEqual(places_count, 1)

    def test_list_admin_areas_geojson_api(self):
        """فحص واجهة التقسيمات الإدارية GeoJSON"""
        response = self.client.get(reverse('admin_areas_geojson'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(data["count"], 2)

    def test_list_categories_api(self):
        """فحص واجهة التصنيفات"""
        response = self.client.get(reverse('place_categories'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        slugs = [c["slug"] for c in data["results"]]
        self.assertIn("healthcare", slugs)
        self.assertIn("religious", slugs)
        healthcare = next(c for c in data["results"] if c["slug"] == "healthcare")
        self.assertEqual(healthcare["places_count"], 1)

    def test_list_places_geojson_api(self):
        """فحص واجهة نقاط الخريطة GeoJSON وفلترة التصنيف"""
        response = self.client.get(reverse('places_geojson') + '?categories=healthcare')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        feature = data["features"][0]
        self.assertEqual(feature["properties"]["title"], "مشفى المواساة الجامعي")
        self.assertEqual(feature["properties"]["sector"], "public")
        self.assertEqual(feature["properties"]["short_number"], "115")

    def test_places_geojson_limit_clamping(self):
        """فحص ضبط حدود عدد النتائج في الـ GeoJSON"""
        res_invalid = self.client.get(reverse('places_geojson') + '?limit=invalid')
        self.assertEqual(res_invalid.status_code, 200)

        res_negative = self.client.get(reverse('places_geojson') + '?limit=-10')
        self.assertEqual(res_negative.status_code, 200)

        res_huge = self.client.get(reverse('places_geojson') + '?limit=99999')
        self.assertEqual(res_huge.status_code, 200)

    def test_place_detail_api(self):
        """فحص بطاقة المنشأة المفصلة مع كافة بيانات الاتصال والقطاع"""
        response = self.client.get(reverse('place_detail', args=[self.place.id]))
        self.assertEqual(response.status_code, 200)
        p = response.json()
        self.assertEqual(p["title"], "مشفى المواساة الجامعي")
        self.assertEqual(p["sector"], "public")
        self.assertEqual(p["sector_label"], "قطاع عام / حكومي")
        self.assertEqual(p["contact"]["short_number"], "115")
        self.assertEqual(p["contact"]["whatsapp"], "963991000000")
        self.assertEqual(p["contact"]["email"], "info@mouwasat-hospital.sy")

    def test_get_place_detail_not_found(self):
        """فحص إرجاع 404 عند طلب مكان غير موجود"""
        response = self.client.get(reverse('place_detail', args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_search_all_api(self):
        """فحص محرك البحث العلوي الشامل مع دعم البلديات والأحياء والشوارع"""
        # بحث عن منشأة
        response = self.client.get(reverse('search_all') + '?q=المواساة')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["title"], "مشفى المواساة الجامعي")
        self.assertIn("counts", data)
        self.assertIn("grouped", data)

        # بحث عن شارع بالبادئة الذكية
        res_street = self.client.get(reverse('search_all') + '?q=شارع فايز')
        self.assertEqual(res_street.status_code, 200)
        data_street = res_street.json()
        self.assertGreaterEqual(data_street["counts"]["streets"], 1)
        self.assertEqual(data_street["grouped"]["streets"][0]["title"], "شارع فايز منصور")
        self.assertEqual(data_street["grouped"]["streets"][0]["type"], "street")

        # بحث عن بلدية
        res_mun = self.client.get(reverse('search_all') + '?q=المزة')
        self.assertEqual(res_mun.status_code, 200)
        data_mun = res_mun.json()
        self.assertGreaterEqual(data_mun["counts"]["municipalities"], 1)

        # بحث أقل من حرفين يرجع نتائج فارغة
        res_short = self.client.get(reverse('search_all') + '?q=م')
        self.assertEqual(res_short.status_code, 200)
        self.assertEqual(res_short.json()["results"], [])
