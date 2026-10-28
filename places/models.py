from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from .text_utils import build_search_index_text
#! جدول التقسيمات الإدارية (AdminArea) مرتبط بنفسه عبر علاقة ForeignKey، ويحتوي على الحقول التالية:
#!Done
class AdminArea(models.Model):
    """
    التقسيمات الإدارية الرسمية (محافظة دمشق -> البلديات والدوائر الخدمية -> الأحياء)
    Level 4: المحافظة (Damascus)
    Level 9: البلدية / الدائرة الخدمية (Municipality)
    Level 10: الحي (Neighborhood)
    """
    name_ar = models.CharField(max_length=150, verbose_name="الاسم بالعربية", db_index=True)
    name_en = models.CharField(max_length=150, blank=True, verbose_name="الاسم بالإنجليزية")
    code = models.CharField(max_length=50, verbose_name="الرمز الإداري")
    pcode = models.CharField(max_length=50, blank=True, null=True, verbose_name="P-Code")
    level = models.IntegerField(verbose_name="المستوى الإداري", db_index=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="المنطقة الأب"
    )
    boundary = models.JSONField(verbose_name="مضلع الحدود الجغرافية GeoJSON")
    search_text = models.CharField(max_length=500, blank=True, db_index=True, verbose_name="نص البحث المعاير")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_areas'
        verbose_name = "منطقة إدارية"
        verbose_name_plural = "التقسيمات الإدارية"
        ordering = ['level', 'id']
        indexes = [
            models.Index(fields=['level', 'code']),
            models.Index(fields=['search_text']),
        ]

    def save(self, *args, **kwargs):
        parent_name = self.parent.name_ar if self.parent else ""
        self.search_text = build_search_index_text(self.name_ar, self.name_en, parent_name, self.code)
        super().save(*args, **kwargs)

    def __str__(self):
        level_label = "حي" if self.level == 10 else "بلدية" if self.level == 9 else "محافظة"
        return f"{level_label}: {self.name_ar} ({self.code})"

#! جدول الشوارع (Street) مرتبط بالحي الإداري (AdminArea) عبر علاقة ForeignKey، ويحتوي على الحقول التالية:
#!Done
class Street(models.Model):
    """
    شوارع وطرقات ومحاور دمشق المعتمدة
    """
    name_ar = models.CharField(max_length=255, verbose_name="اسم الشارع بالعربية", db_index=True)
    name_en = models.CharField(max_length=255, blank=True, verbose_name="اسم الشارع بالإنجليزية")
    highway_type = models.CharField(max_length=50, default="residential", verbose_name="نوع الطريق")
    admin_area = models.ForeignKey(
        AdminArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='streets',
        verbose_name="الحي / البلدية"
    )
    center_lat = models.FloatField(verbose_name="خط العرض المركزي")
    center_lon = models.FloatField(verbose_name="خط الطول المركزي")
    bbox = models.JSONField(verbose_name="حدود الشارع [minLon, minLat, maxLon, maxLat]")
    geometry = models.JSONField(verbose_name="مسار الشارع GeoJSON")
    search_text = models.CharField(max_length=400, blank=True, db_index=True, verbose_name="نص البحث المعاير")
    is_active = models.BooleanField(default=True, verbose_name="نشط")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'streets'
        verbose_name = "شارع / طريق"
        verbose_name_plural = "شوارع وطرقات دمشق"
        ordering = ['name_ar']
        indexes = [
            models.Index(fields=['name_ar']),
            models.Index(fields=['search_text']),
        ]

    def save(self, *args, **kwargs):
        admin_name = self.admin_area.name_ar if self.admin_area else ""
        self.search_text = build_search_index_text(self.name_ar, self.name_en, admin_name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name_ar

#!! جدول التصنيفات الرئيسية (Category) مرتبط بالتصنيفات الفرعية (SubCategory) عبر علاقة ForeignKey، ويحتوي على الحقول التالية:
#!Done

class Category(models.Model):
    """
    تصنيف الطبقة الرئيسية (المشافي، المدارس، المباني الحكومية، النقل، السياحة...)
    """
    name_ar = models.CharField(max_length=100, verbose_name="اسم التصنيف بالعربية")
    name_en = models.CharField(max_length=100, blank=True, verbose_name="اسم التصنيف بالإنجليزية")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="المعرف البرمجي")
    icon = models.CharField(max_length=50, default="map-pin", verbose_name="رمز الأيقونة")
    # color = models.CharField(max_length=20, default="#064239", verbose_name="لون الطبقة")
    is_active = models.BooleanField(default=True, verbose_name="مفعل على الخريطة")
    sort_order = models.IntegerField(default=0, verbose_name="ترتيب العرض")

    class Meta:
        db_table = 'categories'
        verbose_name = "تصنيف طبقة"
        verbose_name_plural = "تصنيفات الطبقات"
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name_ar

    @property
    def places(self):
        """
        الوصول إلى الأماكن التابعة للتصنيف عبر التصنيفات الفرعية (يحفظ التوافقية البرمجية)
        """
        return Place.objects.filter(sub_category__category=self)

#! جدول الاصناف الفرعية (SubCategory) مرتبط بالتصنيف الرئيسي (Category) عبر علاقة ForeignKey، ويحتوي على الحقول التالية:
#!Done

class SubCategory(models.Model):
    """
    التصنيف الفرعي (مثلاً: مشفى حكومي، مركز صحي، مدرسة ابتدائية، وزارة، مديرية...)
    """
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='subcategories',
        verbose_name="التصنيف الرئيسي"
    )
    name_ar = models.CharField(max_length=100, verbose_name="اسم التصنيف الفرعي")
    name_en = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(max_length=100)
    icon = models.CharField(max_length=50, blank=True, null=True, verbose_name="أيقونة مخصصة (اختياري)")
    # color = models.CharField(max_length=20, blank=True, null=True, verbose_name="لون مخصص (اختياري)")
    #is_private = models.BooleanField(default=False, verbose_name="قطاع خاص (تاريخي)")

    class Meta:
        db_table = 'subcategories'
        verbose_name = "تصنيف فرعي"
        verbose_name_plural = "التصنيفات الفرعية"
        unique_together = ('category', 'slug')

    def __str__(self):
        return f"{self.category.name_ar} - {self.name_ar}"

    @property
    def effective_icon(self):
        """
        ترجع أيقونة التصنيف الفرعي إذا وُجدت، وإلا ترجع أيقونة التصنيف الرئيسي كقيمة افتراضية ذكية
        """
        return self.icon or (self.category.icon if self.category else "map-pin")

    @property
    def effective_color(self):
        """
        ترجع لون التصنيف الفرعي إذا وُجد، وإلا ترجع لون التصنيف الرئيسي كقيمة افتراضية
        """
        return self.color or (self.category.color if self.category else "#064239")

#! جدول الاماكن
#!Done
# حدود الإحداثيات المسموحة
LAT_MIN = 33.40
LAT_MAX = 33.62
LON_MIN = 36.14
LON_MAX = 36.42


class Place(models.Model):
    """
    المكان / النقطة الجغرافية (POI).
    """

    # المعلومات الأساسية
    title_ar = models.CharField(
        max_length=255,
        verbose_name="اسم المنشأة/المكان",
        db_index=True
    )

    title_en = models.CharField(
        max_length=255,
        blank=True
    )

    description = models.TextField(
        blank=True,
        verbose_name="الوصف"
    )

    # التصنيف الفرعي
    sub_category = models.ForeignKey(
        SubCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='places',
        verbose_name="التصنيف الفرعي"
    )

    # المنطقة الإدارية
    admin_area = models.ForeignKey(
        AdminArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='places',
        verbose_name="الحي الإداري"
    )

    # القطاع: Public / private / joint
    sector = models.CharField(
        max_length=20,
        default='Public',
        db_index=True,
        verbose_name="القطاع"
    )

    # خط العرض ضمن الحدود المسموحة
    latitude = models.FloatField(
        null=False,
        blank=False,
        validators=[
            MinValueValidator(LAT_MIN),
            MaxValueValidator(LAT_MAX),
        ],
        verbose_name="خط العرض (Lat)"
    )

    # خط الطول ضمن الحدود المسموحة
    longitude = models.FloatField(
        null=False,
        blank=False,
        validators=[
            MinValueValidator(LON_MIN),
            MaxValueValidator(LON_MAX),
        ],
        verbose_name="خط الطول (Lon)"
    )

    location_text = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="العنوان النصي"
    )

    # ساعات العمل
    opening_hours = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="ساعات العمل"
    )

    # ضبط الجودة
    is_verified = models.BooleanField(
        default=True,
        verbose_name="موثق رسمياً"
    )

    is_visible = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="ظاهر على الخريطة"
    )

    # النص المستخدم للبحث
    search_text = models.CharField(
        max_length=600,
        blank=True,
        db_index=True,
        verbose_name="نص البحث المعاير"
    )

    # التواريخ
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        db_table = 'places'
        verbose_name = "مكان / نقطة اهتمام"
        verbose_name_plural = "الأماكن ونقاط الاهتمام"

        ordering = ['title_ar']

        indexes = [
            models.Index(
                fields=['is_visible', 'search_text']
            ),
        ]

        constraints = [
            # حتى يمكن اختيار أساسي إعدادي ثانوي...
            # القيم المسموحة للقطاع فقط
            # models.CheckConstraint(
            #     condition=models.Q(
            #         sector__in=['Public', 'private', 'joint']
            #     ),
            #     name='places_sector_valid'
            # ),

            # حدود خط العرض
            models.CheckConstraint(
                condition=(
                    models.Q(latitude__gte=LAT_MIN) &
                    models.Q(latitude__lte=LAT_MAX)
                ),
                name='places_latitude_valid'
            ),

            # حدود خط الطول
            models.CheckConstraint(
                condition=(
                    models.Q(longitude__gte=LON_MIN) &
                    models.Q(longitude__lte=LON_MAX)
                ),
                name='places_longitude_valid'
            ),
        ]

    def save(self, *args, **kwargs):
        admin_name = (
            self.admin_area.name_ar
            if self.admin_area else ""
        )

        cat_name = (
            self.sub_category.name_ar
            if self.sub_category else ""
        )

        self.search_text = build_search_index_text(
            self.title_ar,
            self.title_en,
            admin_name,
            cat_name,
            self.location_text
        )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title_ar

    @property
    def category(self):
        """
        اشتقاق التصنيف الرئيسي من التصنيف الفرعي.
        """
        return (
            self.sub_category.category
            if self.sub_category else None
  
        )
    
#!جدول معلومات التواصل (CommunicationInfo) مرتبط بالمكان (Place) عبر علاقة ForeignKey، ويحتوي على الحقول التالية:
#!Done

class CommunicationInfo(models.Model):
    """
    معلومات التواصل الخاصة بالمكان.
    """

    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name='communication_info',
        verbose_name="المكان"
    )

    value = models.CharField(
        max_length=200,
        verbose_name="قيمة التواصل"
    )

    type = models.CharField(
        max_length=50,
        choices=[
            ('phone', 'هاتف'),
            ('mobile', 'موبايل'),
            ('whatsapp', 'واتساب'),
            ('email', 'بريد إلكتروني'),
            ('website', 'موقع إلكتروني'),
            ('facebook', 'فيسبوك'),
            ('instagram', 'إنستغرام'),
            ('telegram', 'تيليغرام'),
        ],
        verbose_name="نوع التواصل"
    )
    class Meta:
        db_table = 'communication_info'

    def __str__(self):
        return f"{self.get_type_display()}: {self.value}"


#! جدول الوسائط (PlaceMedia) مرتبط بالمكان (Place) عبر علاقة ForeignKey، ويحتوي على الحقول التالية:
#!Done
class PlaceMedia(models.Model):
    """
    معرض الوسائط والصور الخاص بالمكان
    """
    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name='media',
        verbose_name="المكان"
    )
    file_url = models.CharField(max_length=500, verbose_name="رابط الصورة/الملف")
    media_type = models.CharField(
        max_length=20,
        choices=[('image', 'صورة'), ('document', 'مستند'), ('video', 'فيديو')],
        default='image'
    )
    caption = models.CharField(max_length=255, blank=True, verbose_name="عنوان توضيحي")
    is_cover = models.BooleanField(default=False, verbose_name="صورة رئيسية للغلاف")
    #order = models.IntegerField(default=1, verbose_name="ترتيب العرض")

    class Meta:
        db_table = 'place_media'
        verbose_name = "وسيط / صورة"
        verbose_name_plural = "معرض الوسائط"
       # ordering = ['order', 'id']

    def __str__(self):
        return f"Media for {self.place.title_ar} ({self.media_type})"


#! جدول الباصات (Bus) مرتبط بخطوط النقل العام، ويحتوي على الحقول التالية:
#!Done

class Bus(models.Model):
    """BUS: one record per transport line; prices are Syrian pounds."""
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=150)
    color = models.CharField(max_length=20, default='#3a6962')
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    new_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'buses'
        constraints = [
            models.CheckConstraint(condition=models.Q(old_price__gte=0) | models.Q(old_price__isnull=True), name='bus_old_price_nonnegative'),
            models.CheckConstraint(condition=models.Q(new_price__gte=0) | models.Q(new_price__isnull=True), name='bus_new_price_nonnegative'),
        ]

    def __str__(self):
        return self.name

    # Compatibility values for existing API consumers; these are not columns.
    @property
    def code(self):
        return str(self.pk)

    @property
    def name_en(self):
        return ''


#! جدول مسارات الباصات (BusRoute) مرتبط بالباص (Bus) عبر علاقة ForeignKey، ويحتوي على الحقول التالية:
class BusRoute(models.Model):
    """BUS_ROUTE: historical versions for each direction of a line."""
    id = models.BigAutoField(primary_key=True)
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='routes')
    version = models.PositiveIntegerField(default=1)
    geometry = models.JSONField(db_column='lineString')
    distance = models.FloatField(default=0, help_text='Metres')
    trip_time = models.PositiveIntegerField(default=0, help_text='Minutes')
    direction = models.CharField(max_length=50, choices=[('outbound', 'ذهاب'), ('inbound', 'إياب')])
    start_point = models.CharField(max_length=150, blank=True)
    end_point = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        db_table = 'bus_routes'
        constraints = [
            models.UniqueConstraint(fields=['bus', 'direction', 'version'], name='bus_route_unique_version'),
            models.UniqueConstraint(fields=['bus', 'direction'], condition=models.Q(is_active=True), name='bus_route_one_active_direction'),
            models.CheckConstraint(condition=models.Q(version__gte=1), name='bus_route_positive_version'),
            models.CheckConstraint(condition=models.Q(distance__gte=0), name='bus_route_distance_nonnegative'),
            models.CheckConstraint(condition=models.Q(direction__in=['outbound', 'inbound']), name='bus_route_valid_direction'),
        ]

    def __str__(self):
        return f'{self.bus.name} ({self.direction}, v{self.version})'

    # Preserve existing API units without retaining a third table.
    @property
    def specifications(self):
        return self

    @property
    def cost(self):
        return self.bus.new_price if self.bus.new_price is not None else 0

    @property
    def route_length_km(self):
        return self.distance / 1000

    @property
    def trip_time_minutes(self):
        return self.trip_time

#! [] جدول التنبيهات والإشعارات (Notification) مرتبط بالمكان (Place) عبر علاقة ForeignKey، ويحتوي على الحقول التالية:

class Notification(models.Model):
    """
    إشعارات وتنبيهات الخريطة (أعمال صيانة طرق، تعديل مسار باص، إغلاقات...)
    """

    title = models.CharField(max_length=200, verbose_name="عنوان الإشعار")
    content = models.TextField(verbose_name="نص الإشعار")
    urgency = models.CharField(max_length=20, choices=[
        ('low', 'منخفض'),
        ('medium', 'متوسط'),
        ('high', 'عالي / طارئ'),
    ], default='medium', verbose_name="درجة الأهمية")
    start_date = models.DateTimeField( verbose_name="تاريخ البدء")
    expiration_date = models.DateTimeField( verbose_name="تاريخ الانتهاء")
    latitude = models.FloatField(null=True, blank=True, verbose_name="خط العرض (اختياري)")
    longitude = models.FloatField(null=True, blank=True, verbose_name="خط الطول (اختياري)")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        db_table = 'notifications'
        verbose_name = "إشعار خريطة"
        verbose_name_plural = "إشعارات الخريطة"
        ordering = ['-start_date']

    def __str__(self):
        return f"[{self.urgency}] {self.title}"

#! جدول سجل العمليات والتدقيق (LogEntry) لتتبع التغييرات والإجراءات في النظام، ويحتوي على الحقول التالية:
class Log(models.Model):
    """
    سجل العمليات والتدقيق (LOG_TABLE)
    """
    action = models.CharField(max_length=100, verbose_name="نوع الإجراء")
    actor = models.CharField(max_length=100, blank=True, verbose_name="المستخدم أو المعرف")
    details = models.JSONField(default=dict, blank=True, verbose_name="التفاصيل")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'logs'
        verbose_name = "سجل تدقيق"
        verbose_name_plural = "سجلات التدقيق"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} at {self.created_at}"

