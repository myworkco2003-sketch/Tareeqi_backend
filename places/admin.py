from django.contrib import admin
from .models import (
    AdminArea, Street, Category, SubCategory, Place, PlaceMedia,
    Bus, BusRoute, Notification, Log
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'name_en', 'slug', 'icon', 'color', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name_ar', 'name_en', 'slug')
    ordering = ('sort_order', 'id')


@admin.register(Street)
class StreetAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'name_en', 'highway_type', 'admin_area', 'is_active')
    list_filter = ('highway_type', 'is_active')
    search_fields = ('name_ar', 'name_en')
    ordering = ('name_ar',)


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'category', 'slug', 'icon', 'color')
    list_filter = (['category'])
    search_fields = ('name_ar', 'slug')
    ordering = ('category', 'name_ar')


class PlaceMediaInline(admin.TabularInline):
    model = PlaceMedia
    extra = 1


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ('title_ar', 'title_en', 'sub_category', 'sector', 'admin_area', 'is_verified', 'is_visible')
    list_filter = ('sector', 'sub_category__category', 'sub_category', 'is_verified', 'is_visible')
    search_fields = ('title_ar', 'title_en', 'description')
    inlines = [PlaceMediaInline]
    fieldsets = (
        ("المعلومات الأساسية", {
            "fields": ("title_ar", "title_en", "description", "sub_category", "sector", "admin_area")
        }),
        ("الموقع الجغرافي", {
            "fields": ("latitude", "longitude", "location_text")
        }),
        ("معلومات الاتصال (الهاتف، الموبايل، الواتساب)", {
            "fields": ("phone", "mobile", "short_number", "whatsapp", "email", "website", "social_media", "opening_hours")
        }),
        ("التحكم وضبط الجودة", {
            "fields": ("is_verified", "is_visible")
        }),
    )


@admin.register(AdminArea)
class AdminAreaAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'name_en', 'code', 'level', 'parent')
    list_filter = ('level',)
    search_fields = ('name_ar', 'name_en', 'code')


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ('name', 'color', 'old_price', 'new_price', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(BusRoute)
class BusRouteAdmin(admin.ModelAdmin):
    list_display = ('bus', 'direction', 'version', 'is_active')
    list_filter = ('direction', 'is_active')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('content', 'urgency', 'start_date', 'expiration_date', 'is_active')
    list_filter = ('urgency', 'is_active')


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ('action', 'actor', 'created_at')
    list_filter = ('action',)
    search_fields = ('action', 'actor')
