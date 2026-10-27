from django.urls import path
from . import views

urlpatterns = [
    # التقسيمات الإدارية المعتمدة
    path('admin-areas/', views.list_admin_areas_geojson, name='admin_areas_geojson'),
    
    # تصنيفات الطبقات
    path('categories/', views.list_categories, name='place_categories'),
    
    # نقاط الأماكن والمنشآت للطبقات (GeoJSON)
    path('places/geojson/', views.list_places_geojson, name='places_geojson'),
    
    # تفاصيل منشأة محددة (Market Card)
    path('places/<int:place_id>/', views.get_place_detail, name='place_detail'),
    
    # البحث الشامل العلوي (Auto-suggest Search Bar)
    path('search/', views.search_all, name='search_all'),
    
    # شبكة المواصلات العامة
    path('transit/lines/', views.list_transit_lines, name='transit_lines'),
    path('transit/all-routes-geojson/', views.list_all_transit_routes_geojson, name='transit_all_routes_geojson'),
    path('transit/routes/<int:route_id>/', views.get_transit_route_geojson, name='transit_route_geojson'),
    
    # محرك التوجيه والوصول إلى المكان (Transit / Car / Walk)
    path('routing/', views.calculate_route, name='calculate_route'),
    
    # التنبيهات والإشعارات
    path('notifications/', views.list_notifications, name='notifications'),
]
