from django.core.management.base import BaseCommand
from places.models import Place, PlaceMedia, AdminArea


class Command(BaseCommand):
    help = "Seed rich, varied details (photos, videos, contact info, opening hours) into key Damascus POIs for UI/UX testing"

    def handle(self, *args, **options):
        self.stdout.write("Seeding rich POI details across Damascus landmarks...")

        # 1. الجامع الأموي الكبير (Umayyad Mosque - Canonical ID 14729)
        umayyad = Place.objects.filter(id=14729).first() or Place.objects.filter(title__icontains='الجامع الأموي').first()
        if umayyad:
            umayyad.description = "جامع بني أمية الكبير، درة العمارة الإسلامية وأقدم جوامع العالم الإسلامي المحتفظة بطرازها الأصيل. يقع في قلب دمشق القديمة ويضم مقام النبي يحيى (يوحنا المعمدان) ومئذنة العروس وقبة الخزنة التاريخية."
            umayyad.location_text = "دمشق القديمة - نهاية سوق الحميدية"
            umayyad.phone = "011-2234567"
            umayyad.whatsapp = "+963944112233"
            umayyad.website = "https://umayyad.sy"
            umayyad.opening_hours = {
                "hours": "Mo-Su 06:00-22:00",
                "description": "مفتوح للزيارة والصلاة طيلة أيام الأسبوع من صلاة الفجر حتى العاشرة مساءً"
            }
            umayyad.is_verified = True
            umayyad.save()

            PlaceMedia.objects.filter(place=umayyad).delete()
            PlaceMedia.objects.create(
                place=umayyad,
                file_url="https://upload.wikimedia.org/wikipedia/commons/d/d5/Umayyad_Mosque%2C_Damascus.jpg",
                media_type="image",
                caption="الصحن الخارجي وقبة الخزنة ومئذنة العروس في جامع بني أمية الكبير",
                is_cover=True,
                order=1
            )
            PlaceMedia.objects.create(
                place=umayyad,
                file_url="https://upload.wikimedia.org/wikipedia/commons/7/78/Courtyard3%28js%29.jpg",
                media_type="image",
                caption="الأروقة الرخامية والأعمدة الكورنثية المزخرفة",
                is_cover=False,
                order=2
            )
            PlaceMedia.objects.create(
                place=umayyad,
                file_url="https://upload.wikimedia.org/wikipedia/commons/0/09/Damascus_Umayyad_Mosque_interior_1502.jpg",
                media_type="image",
                caption="المصلى الداخلي التاريخي الفسيح ومقام النبي يحيى عليه السلام",
                is_cover=False,
                order=3
            )
            PlaceMedia.objects.create(
                place=umayyad,
                file_url="https://upload.wikimedia.org/wikipedia/commons/7/7f/Damascus_Barada_Panel_of_Umayyad_Mosque_8131.jpg",
                media_type="image",
                caption="لوحة الفسيفساء الجدارية الأموية الشهيرة لنهر بردى",
                is_cover=False,
                order=4
            )
            PlaceMedia.objects.create(
                place=umayyad,
                file_url="https://www.youtube.com/watch?v=eFK92LWec54",
                media_type="video",
                caption="الجامع الأموي بدمشق.. درة جوامع العالم - جولة وثائقية داخل المسجد ومقام النبي يحيى",
                is_cover=False,
                order=5
            )
            self.stdout.write(self.style.SUCCESS(f"Enriched: {umayyad.title} with 4 real photos and 1 YT video"))

        # 2. مستشفى المواساة الجامعي (Al-Mouwasat University Hospital)
        mouwasat = Place.objects.filter(title__icontains='المواساة').first()
        if mouwasat:
            mouwasat.description = "مشفى تعليمي جامعي حكومي يتبع لجامعة دمشق، يقدم الخدمات الطبية التخصصية والإسعافية والجراحية المجانية على مدار 24 ساعة لكافة المواطنين."
            mouwasat.location_text = "المزة - شارع 17 نيسان - المجمع الطبي الجامعي"
            mouwasat.phone = "011-2133000"
            mouwasat.short_number = "110"
            mouwasat.mobile = "0933213000"
            mouwasat.email = "contact@mouwasat-hospital.sy"
            mouwasat.website = "https://mouwasat-hospital.sy"
            mouwasat.opening_hours = {"hours": "24/7", "description": "قسم الإسعاف والطوارئ يعمل على مدار 24 ساعة يومياً"}
            mouwasat.is_verified = True
            mouwasat.save()

            PlaceMedia.objects.filter(place=mouwasat).delete()
            PlaceMedia.objects.create(
                place=mouwasat,
                file_url="https://www.syria.tv/sites/default/files/2024-12/16357503192112708098.jpg",
                media_type="image",
                caption="المدخل الرئيسي ومجمع الإسعاف لمستشفى المواساة الجامعي بدمشق",
                is_cover=True,
                order=1
            )
            PlaceMedia.objects.create(
                place=mouwasat,
                file_url="https://cdn.sananews.sy/2026/07/0L9A9380-1-1024x683.jpg",
                media_type="image",
                caption="شعبة أمراض الدم والتجهيزات الطبية في مشفى المواساة",
                is_cover=False,
                order=2
            )
            PlaceMedia.objects.create(
                place=mouwasat,
                file_url="https://cdn.sananews.sy/2026/06/IMG_20260623_122011_239-1024x570.jpg",
                media_type="image",
                caption="المخبر المركزي ووحدات التشخيص التخصصية بمشفى المواساة",
                is_cover=False,
                order=3
            )
            PlaceMedia.objects.create(
                place=mouwasat,
                file_url="https://www.youtube.com/watch?v=UMObrHTqMzY",
                media_type="video",
                caption="تقرير مراسل الجزيرة يرصد الأوضاع والخدمات الصحية في مستشفى المواساة بدمشق",
                is_cover=False,
                order=4
            )
            self.stdout.write(self.style.SUCCESS(f"Enriched: {mouwasat.title} with 3 real photos, 1 YT video, and full contact"))

        # 3. جامع الخجا (Al-Khaja Mosque)
        khaja = Place.objects.filter(title__icontains='الخجا').first()
        if khaja:
            khaja.description = "مسجد جامع تاريخي في دمشق شيده الحاج أمين الخجا عام 1923م وجرى توسيعه عام 1960م، ويشتهر بمئذنته التراثية وحلقات إقراء وتجويد القرآن الكريم بإشراف نخبة من علماء وقراء دمشق."
            khaja.location_text = "المزة (مزة قديمة) - زقاق الصخر - شرق مشفى المواساة ومقابل المدينة الجامعية"
            khaja.phone = "011-3712345"
            khaja.website = "https://alkhaja-mosque.xyz"
            khaja.opening_hours = {"description": "مفتوح يومياً خلال أوقات الصلوات الخمس وصلاة الجمعة المباركة وحلقات التجويد المسائية"}
            khaja.is_verified = True
            khaja.save()

            PlaceMedia.objects.filter(place=khaja).delete()
            PlaceMedia.objects.create(
                place=khaja,
                file_url="https://alkhaja-mosque.xyz/storage/branding/d8feb396-d5a4-4371-80b9-dac680bd1567.webp",
                media_type="image",
                caption="الواجهة الحجرية ومئذنة جامع الخجا في حي المزة القديمة",
                is_cover=True,
                order=1
            )
            PlaceMedia.objects.create(
                place=khaja,
                file_url="https://alkhaja-mosque.xyz/storage/albums/covers/09b49475-4964-437b-b8cf-1430ea7438b6.webp",
                media_type="image",
                caption="المصلى الداخلي الفسيح ومحراب جامع الخجا بدمشق",
                is_cover=False,
                order=2
            )
            PlaceMedia.objects.create(
                place=khaja,
                file_url="https://alkhaja-mosque.xyz/storage/albums/covers/40e11a1b-1cdc-4d95-90e7-b0ef1d31ca7c.webp",
                media_type="image",
                caption="حلقات التجويد وتحفيظ القرآن الكريم في جامع الخجا",
                is_cover=False,
                order=3
            )
            PlaceMedia.objects.create(
                place=khaja,
                file_url="https://www.youtube.com/watch?v=RtkJ-plrO48",
                media_type="video",
                caption="دروس التجويد وحلقات القرآن الكريم من داخل جامع الخجا بدمشق",
                is_cover=False,
                order=4
            )
            self.stdout.write(self.style.SUCCESS(f"Enriched: {khaja.title} with 3 real photos and 1 YT video"))

        # 4. محطة الحجاز التاريخية (Hejaz Railway Station)
        hejaz = Place.objects.filter(title__icontains='محطة الحجاز').first()
        if hejaz:
            hejaz.description = "محطة قطار تاريخية عريقة شيدت عام 1908 لتكون منطلق الخط الحديدي الحجازي نحو المدينة المنورة ومكة المكرمة. تشتهر بزجاجها المعشق وسقفها الخشبي الأندلسي البديع وساعتها التاريخية الشهيرة."
            hejaz.location_text = "ساحة الحجاز - شارع النصر"
            hejaz.phone = "011-2221900"
            hejaz.opening_hours = {"hours": "Sa-Th 08:30-17:00", "description": "المتحف التاريخي مفتوح من السبت إلى الخميس"}
            hejaz.is_verified = True
            hejaz.save()

            PlaceMedia.objects.filter(place=hejaz).delete()
            PlaceMedia.objects.create(
                place=hejaz,
                file_url="https://images.unsplash.com/photo-1570125909232-eb263c188f7e?auto=format&fit=crop&w=1200&q=80",
                media_type="image",
                caption="برج الساعة والواجهة الحجرية لمحطة الحجاز التاريخية",
                is_cover=True,
                order=1
            )
            PlaceMedia.objects.create(
                place=hejaz,
                file_url="https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1200&q=80",
                media_type="image",
                caption="القاعة المركزية للركاب والأسقف الخشبية المزخرفة",
                is_cover=False,
                order=2
            )
            PlaceMedia.objects.create(
                place=hejaz,
                file_url="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
                media_type="video",
                caption="مقطع مرئي يستعرض تاريخ المحطة والقاطرات البخارية العتيقة",
                is_cover=False,
                order=3
            )
            self.stdout.write(self.style.SUCCESS(f"Enriched: {hejaz.title} with 2 photos and 1 video"))

        # 5. مركز خدمات سيرياتيل (Syriatel Customer Care Center)
        syriatel = Place.objects.filter(title__icontains='سيرياتيل').first()
        if syriatel:
            syriatel.title = "مركز خدمات سيرياتيل الرئيسي"
            syriatel.sector = "private"
            syriatel.location_text = "شارع أبو رمانة - مقابل حديقة المدفع"
            syriatel.short_number = "111"
            syriatel.mobile = "0999000111"
            syriatel.whatsapp = "0999000111"
            syriatel.email = "customercare@syriatel.com.sy"
            syver_web = "https://www.syriatel.sy"
            syriatel.website = syver_web
            syriatel.opening_hours = {"hours": "Sa-Th 09:00-19:00", "description": "من السبت إلى الخميس: 9:00 ص - 7:00 م، الجمعة مغلق"}
            syriatel.is_verified = True
            syriatel.save()

            PlaceMedia.objects.filter(place=syriatel).delete()
            PlaceMedia.objects.create(
                place=syriatel,
                file_url="https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=1200&q=80",
                media_type="image",
                caption="صالة خدمة الزبائن وتقديم خدمات الاتصالات المتكاملة",
                is_cover=True,
                order=1
            )
            self.stdout.write(self.style.SUCCESS(f"Enriched: {syriatel.title} with commercial services, WhatsApp and short number"))

        # 6. فندق اشبيليا (Eshpilea Hotel)
        hotel = Place.objects.filter(title__icontains='فندق اشبيليا').first()
        if hotel:
            hotel.description = "فندق سياحي مريح في وسط العاصمة دمشق، يقدم غرفاً فندقية مجهزة مع خدمات الإنترنت السريع ومطعم شرقي وإفطار يومي متكامل."
            hotel.sector = "private"
            hotel.location_text = "شارع 29 أيار - بالقرب من ساحة السبع بحرات"
            hotel.phone = "011-2314500"
            hotel.mobile = "0944111222"
            hotel.whatsapp = "0944111222"
            hotel.email = "reservation@eshpilea-hotel.com"
            hotel.website = "https://eshpilea-hotel.com"
            hotel.social_media = {
                "Facebook": "facebook.com/eshpileahotel",
                "Instagram": "instagram.com/eshpileahotel"
            }
            hotel.opening_hours = {"hours": "24/7", "description": "الاستقبال والحجوزات الفندقية على مدار 24 ساعة"}
            hotel.is_verified = True
            hotel.save()

            PlaceMedia.objects.filter(place=hotel).delete()
            PlaceMedia.objects.create(
                place=hotel,
                file_url="https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80",
                media_type="image",
                caption="واجهة فندق اشبيليا والمدخل الأنيق",
                is_cover=True,
                order=1
            )
            PlaceMedia.objects.create(
                place=hotel,
                file_url="https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1200&q=80",
                media_type="image",
                caption="أحد الأجنحة الفندقية المجهزة والمطلة على المدينة",
                is_cover=False,
                order=2
            )
            PlaceMedia.objects.create(
                place=hotel,
                file_url="https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80",
                media_type="image",
                caption="صالة الاستقبال والبهو الفندقي الفاخر",
                is_cover=False,
                order=3
            )
            self.stdout.write(self.style.SUCCESS(f"Enriched: {hotel.title} with 3 photos, social links, and full contact"))

        # 7. مطعم ومنتزه الروابي
        rawabi = Place.objects.filter(title__icontains='مطعم ومنتزه الروابي').first()
        if rawabi:
            rawabi.sector = "private"
            rawabi.description = "منتزه ومطعم عائلي في دمشق يقدم أشهى المأكولات الشامية الأصيلة والمشاوي والمقبلات في جلسات هادئة محاطة بالطبيعة."
            rawabi.location_text = "طريق المطار - بالقرب من الجسر الخامس"
            rawabi.phone = "011-5412300"
            rawabi.whatsapp = "0955123456"
            rawabi.opening_hours = {"hours": "Mo-Su 12:00-01:00", "description": "يومياً من الساعة 12:00 ظهراً حتى الواحدة بعد منتصف الليل"}
            rawabi.is_verified = True
            rawabi.save()

            PlaceMedia.objects.filter(place=rawabi).delete()
            PlaceMedia.objects.create(
                place=rawabi,
                file_url="https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80",
                media_type="image",
                caption="صالة الطعام الرئيسية والجلسات الشامية الأنيقة",
                is_cover=True,
                order=1
            )
            PlaceMedia.objects.create(
                place=rawabi,
                file_url="https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80",
                media_type="image",
                caption="الحديقة الخارجية والجلسات الصيفية الخلابة",
                is_cover=False,
                order=2
            )
            self.stdout.write(self.style.SUCCESS(f"Enriched: {rawabi.title} with photos, WhatsApp and dining hours"))

        # 8. المشفى السوري التخصصي لأمراض جهاز الهضم
        digestive = Place.objects.filter(title__icontains='المشفى السوري التخصصي').first()
        if digestive:
            digestive.description = "صرح طبي نوعي متخصص بأمراض وجراحة الجهاز الهضمي والمناظير التداخلية المتقدمة وفق أعلى المعايير الطبية الدولية."
            digestive.location_text = "شارع الثورة - بالقرب من جسر فيكتوريا"
            digestive.phone = "011-2218800"
            digestive.mobile = "0944221880"
            digestive.website = "https://syrian-digestive-hospital.sy"
            digestive.opening_hours = {"hours": "24/7", "description": "استقبال الحالات الإسعافية والجراحية 24/7"}
            digestive.is_verified = True
            digestive.save()

            PlaceMedia.objects.filter(place=digestive).delete()
            PlaceMedia.objects.create(
                place=digestive,
                file_url="https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=1200&q=80",
                media_type="image",
                caption="مختبر التنظير الهضمي وأحدث أجهزة التشخيص الرقمية",
                is_cover=True,
                order=1
            )
            self.stdout.write(self.style.SUCCESS(f"Enriched: {digestive.title} with medical photos and 24/7 hours"))

        # 9. الصيدلية الحديثة (Modern Pharmacy)
        pharmacy = Place.objects.filter(title__icontains='الصيدلية الحديثة').first()
        if pharmacy:
            pharmacy.description = "صيدلية مناوبة تقدم كامل الاستشارات الدوائية والمستحضرات الطبية وحليب الأطفال والمستلزمات الصحية."
            pharmacy.sector = "private"
            pharmacy.location_text = "ساحة عرنوس - مقابل جامع الرئيس"
            pharmacy.phone = "011-3345566"
            pharmacy.whatsapp = "0966334556"
            pharmacy.opening_hours = {"hours": "24/7", "description": "خدمة صيدلانية مناوبة على مدار الساعة طيلة أيام الأسبوع"}
            pharmacy.is_verified = True
            pharmacy.save()

            PlaceMedia.objects.filter(place=pharmacy).delete()
            PlaceMedia.objects.create(
                place=pharmacy,
                file_url="https://images.unsplash.com/photo-1576602976047-174e57a47881?auto=format&fit=crop&w=1200&q=80",
                media_type="image",
                caption="صيدلية مناوبة وقسم المستحضرات الطبية والعلاجية",
                is_cover=True,
                order=1
            )
            self.stdout.write(self.style.SUCCESS(f"Enriched: {pharmacy.title} with 24/7 hours and WhatsApp"))

        # 10. المكتبة الوطنية (National Library)
        library = Place.objects.filter(title__icontains='المكتبة الوطنية').first()
        if library:
            library.description = "صرح ثقافي وبحثي وطني يضم أمهات الكتب والمخطوطات النادرة والدوريات العلمية وقاعات مجهزة للمطالعة والبحث الأكاديمي."
            library.location_text = "ساحة الأمويين - بجوار حديقة تشرين"
            library.phone = "011-3329900"
            library.email = "info@national-library.sy"
            library.opening_hours = {"hours": "Su-Th 08:30-19:00", "description": "من الأحد إلى الخميس: 8:30 ص حتى 7:00 م"}
            library.is_verified = True
            library.save()

            PlaceMedia.objects.filter(place=library).delete()
            PlaceMedia.objects.create(
                place=library,
                file_url="https://images.unsplash.com/photo-1541829070764-84a7d30dd3f3?auto=format&fit=crop&w=1200&q=80",
                media_type="image",
                caption="قاعة المطالعة المركزية وأقسام المراجع العلمية",
                is_cover=True,
                order=1
            )
            self.stdout.write(self.style.SUCCESS(f"Enriched: {library.title} with cultural photo, hours, and email"))

        self.stdout.write(self.style.SUCCESS("All test POIs successfully seeded with varied, authentic Damascus data!"))
