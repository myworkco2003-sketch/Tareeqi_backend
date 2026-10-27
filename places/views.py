import math
import json
import re
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_GET
from django.db.models import Q
from .models import (
    AdminArea, Street, Category, SubCategory, Place, PlaceMedia, Notification,
    Bus, BusRoute
)
from .text_utils import normalize_arabic, generate_search_variants


def haversine_distance_km(lat1, lon1, lat2, lon2):
    """
    حساب المسافة الجغرافية بالكيلومتر بين نقطتين على الكرة الأرضية
    """
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@require_GET
def list_admin_areas_geojson(request):
    """
    إرجاع التقسيمات الإدارية (البلديات والأحياء) بصيغة GeoJSON القياسية
    """
    level = request.GET.get('level')
    parent_id = request.GET.get('parent_id')

    queryset = AdminArea.objects.select_related('parent').all()

    if level:
        try:
            queryset = queryset.filter(level=int(level))
        except ValueError:
            pass

    if parent_id:
        try:
            queryset = queryset.filter(parent_id=int(parent_id))
        except ValueError:
            pass

    features = []
    for area in queryset:
        features.append({
            "type": "Feature",
            "id": area.id,
            "properties": {
                "id": area.id,
                "name_ar": area.name_ar,
                "name_en": area.name_en,
                "code": area.code,
                "level": area.level,
                "level_name": "بلدية" if area.level == 9 else "حي",
                "parent_id": area.parent_id,
                "parent_name_ar": area.parent.name_ar if area.parent else "",
            },
            "geometry": area.boundary,
        })

    return JsonResponse({
        "type": "FeatureCollection",
        "count": len(features),
        "features": features,
    })


@require_GET
def list_categories(request):
    """
    إرجاع قائمة تصنيفات الطبقات (مشافي، مدارس، مباني حكومية...) مع عدد الأماكن
    """
    categories = Category.objects.filter(is_active=True).prefetch_related('subcategories')
    data = []
    for cat in categories:
        data.append({
            "id": cat.id,
            "slug": cat.slug,
            "name_ar": cat.name_ar,
            "name_en": cat.name_en,
            "icon": cat.icon,
            "color": cat.color,
            "places_count": cat.places.filter(is_visible=True).count(),
            "subcategories": [
                {
                    "id": sub.id,
                    "slug": sub.slug,
                    "name_ar": sub.name_ar,
                    "icon": sub.effective_icon,
                    "color": sub.effective_color,
                    "is_private": sub.is_private,
                }
                for sub in cat.subcategories.all()
            ]
        })
    return JsonResponse({"results": data})


# معرفات معالم الاستدلال الثابتة (Permanent Landmarks) المعروضة مسبقاً بطبقة خاصة على الخريطة
PERMANENT_LANDMARK_IDS = {
    14729, 14730, 13059, 10340, 13080, 14731, 14732, 13175, 14733, 14734,
    14735, 13023, 14736, 14512, 14737, 14738, 14739, 14740, 14741, 10809,
    11208, 14742, 14743, 13014, 13100, 13085, 14744, 13083, 14745, 13069,
    13096, 13239, 13060, 14746, 13178, 13193, 14747, 13077, 13082, 13234,
    13214, 14748
}


@require_GET
def list_places_geojson(request):
    """
    إرجاع نقاط الأماكن والمنشآت بصيغة GeoJSON لطبقات الخريطة النشطة
    يدعم الفلترة حسب:
    - categories: معرفات التصنيفات مفصولة بفواصل (e.g. healthcare,education,government)
    - admin_area_id: فلترة حسب الحي
    - limit: الحد الأقصى للنقاط (الافتراضي: 1500)
    - include_permanent: افتراضياً 0 لاستبعاد المعالم الثابتة لمنع ظهور دوائر مكررة فوق شاراتها
    """
    cat_param = request.GET.get('categories')
    subcat_param = request.GET.get('subcategories')
    admin_id = request.GET.get('admin_area_id')
    include_permanent = request.GET.get('include_permanent', '0') == '1'
    try:
        limit = int(request.GET.get('limit', 1500))
    except (TypeError, ValueError):
        limit = 1500
    # Bound the payload: this endpoint is public and unbounded slices let a
    # single request serialise the entire table.
    limit = max(1, min(limit, 5000))

    queryset = Place.objects.filter(is_visible=True, latitude__isnull=False, longitude__isnull=False).select_related('sub_category__category', 'admin_area')

    # منع التكرار الكارتوغرافي: استبعاد المعالم الدائمة التي تعرضها طبقة landmarks مسبقاً
    if not include_permanent:
        queryset = queryset.exclude(id__in=PERMANENT_LANDMARK_IDS)

    if cat_param:
        slugs = [s.strip() for s in cat_param.split(',') if s.strip()]
        if slugs:
            queryset = queryset.filter(sub_category__category__slug__in=slugs)

    if subcat_param:
        sub_slugs = [s.strip() for s in subcat_param.split(',') if s.strip()]
        if sub_slugs:
            queryset = queryset.filter(sub_category__slug__in=sub_slugs)

    if admin_id:
        try:
            queryset = queryset.filter(admin_area_id=int(admin_id))
        except ValueError:
            pass

    queryset = queryset[:limit]

    features = []
    for p in queryset:
        features.append({
            "type": "Feature",
            "id": p.id,
            "geometry": {
                "type": "Point",
                "coordinates": [p.longitude, p.latitude],
            },
            "properties": {
                "id": p.id,
                "title": p.title,
                "title_en": p.title_en,
                "category_slug": p.category.slug if p.category else "",
                "category_name": p.category.name_ar if p.category else "",
                "category_icon": p.category.icon if p.category else "map-pin",
                "category_color": p.category.color if p.category else "#064239",
                "sub_category_slug": p.sub_category.slug if p.sub_category else "",
                "sub_category_name": p.sub_category.name_ar if p.sub_category else "",
                "sub_category_icon": p.sub_category.effective_icon if p.sub_category else "map-pin",
                "sub_category_color": p.sub_category.effective_color if p.sub_category else "#064239",
                "sector": p.sector,
                "sector_label": p.get_sector_display(),
                "admin_area_name": p.admin_area.name_ar if p.admin_area else "",
                "phone": p.phone,
                "mobile": p.mobile,
                "short_number": p.short_number,
                "whatsapp": p.whatsapp,
                "is_verified": p.is_verified,
            }
        })

    return JsonResponse({
        "type": "FeatureCollection",
        "count": len(features),
        "features": features,
    })


@require_GET
def get_place_detail(request, place_id):
    """
    إرجاع التفاصيل الكاملة لمكان محدد لعرضها في بطاقة المنشأة (Market Card)
    """
    try:
        p = Place.objects.select_related('sub_category__category', 'admin_area__parent').prefetch_related('media').get(id=place_id)
    except Place.DoesNotExist:
        raise Http404("المكان غير موجود")

    media_list = [
        {
            "id": m.id,
            "url": m.file_url,
            "type": m.media_type,
            "caption": m.caption,
            "is_cover": m.is_cover,
        }
        for m in p.media.all()
    ]

    municipality_name = p.admin_area.parent.name_ar if (p.admin_area and p.admin_area.parent) else ""
    neighborhood_name = p.admin_area.name_ar if p.admin_area else ""

    return JsonResponse({
        "id": p.id,
        "title": p.title,
        "title_en": p.title_en,
        "description": p.description,
        "sector": p.sector,
        "sector_label": p.get_sector_display(),
        "category": {
            "id": p.category.id if p.category else None,
            "name_ar": p.category.name_ar if p.category else "",
            "slug": p.category.slug if p.category else "",
            "icon": p.category.icon if p.category else "map-pin",
            "color": p.category.color if p.category else "#064239",
        },
        "sub_category": {
            "name_ar": p.sub_category.name_ar if p.sub_category else "",
            "icon": p.sub_category.effective_icon if p.sub_category else "map-pin",
            "color": p.sub_category.effective_color if p.sub_category else "#064239",
            "is_private": p.sub_category.is_private if p.sub_category else False,
        },
        "location": {
            "latitude": p.latitude,
            "longitude": p.longitude,
            "address_text": p.location_text or f"دمشق - {neighborhood_name}",
            "neighborhood": neighborhood_name,
            "municipality": municipality_name,
        },
        "contact": {
            "phone": p.phone,
            "mobile": p.mobile,
            "short_number": p.short_number,
            "whatsapp": p.whatsapp,
            "email": p.email,
            "website": p.website,
            "social_media": p.social_media,
            "opening_hours": p.opening_hours,
        },
        "is_verified": p.is_verified,
        "media": media_list,
    })


HIGHWAY_LABELS = {
    'motorway': 'أوتوستراد سريع',
    'trunk': 'محور شرياني رئيسي',
    'trunk_link': 'وصلة محورية',
    'primary': 'شارع رئيسي',
    'secondary': 'شارع فرعي رابط',
    'tertiary': 'شارع محلي',
    'residential': 'شارع سكني',
    'pedestrian': 'شارع مشاة / سوق',
    'service': 'طريق خدمي',
}


def strip_arabic_prefixes(query: str) -> str:
    """إزالة البوادئ الشائعة للبحث الذكي (مثل: شارع، حي، بلدية، دائرة خدمات)"""
    cleaned = re.sub(r'^(شارع|طريق|جادة|حي|بلدية|دائرة خدمات|دائرة|منطقة|سرفيس|خط)\s+', '', query.strip()).strip()
    return cleaned if len(cleaned) >= 2 else query.strip()


@require_GET
def search_all(request):
    """
    البحث الشامل الفوري (شريط البحث العلوي Damascene Search Bar):
    يبحث في:
    1. الأماكن والمنشآت (مشافي، مدارس، مراكز حكومية، معالم...)
    2. التقسيمات الإدارية (البلديات والأحياء)
    3. خطوط الباصات والنقل العام
    """
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({"results": [], "grouped": {}, "counts": {"all": 0}, "query": query})

    norm_query = normalize_arabic(query)
    variants = generate_search_variants(query)

    # مرشحات البحث للتقسيمات الإدارية
    q_admin = Q()
    for v in variants:
        q_admin |= Q(search_text__icontains=v)
    q_admin |= Q(name_en__icontains=query) | Q(code__icontains=query)

    # 1. البلديات (Municipalities - Level 9)
    municipalities = []
    mun_qs = AdminArea.objects.filter(level=9).filter(q_admin)[:20]
    for a in mun_qs:
        coords = [36.295, 33.513]
        if a.boundary and a.boundary.get("coordinates"):
            try:
                poly = a.boundary["coordinates"][0]
                if isinstance(poly[0], list) and isinstance(poly[0][0], list):
                    poly = poly[0]
                coords = [sum(pt[0] for pt in poly) / len(poly), sum(pt[1] for pt in poly) / len(poly)]
            except Exception:
                pass
        municipalities.append({
            "type": "municipality",
            "id": a.id,
            "title": a.name_ar,
            "subtitle": "بلدية رسمية • محافظة دمشق",
            "code": a.code,
            "level": 9,
            "icon": "landmark",
            "color": "#c8a76a",
            "coordinates": coords,
            "boundary": a.boundary,
        })

    # 2. الأحياء السكنية (Neighborhoods - Level 10)
    neighborhoods = []
    neigh_qs = AdminArea.objects.filter(level=10).filter(q_admin).select_related('parent')[:30]
    for a in neigh_qs:
        coords = [36.295, 33.513]
        if a.boundary and a.boundary.get("coordinates"):
            try:
                poly = a.boundary["coordinates"][0]
                if isinstance(poly[0], list) and isinstance(poly[0][0], list):
                    poly = poly[0]
                coords = [sum(pt[0] for pt in poly) / len(poly), sum(pt[1] for pt in poly) / len(poly)]
            except Exception:
                pass
        parent_title = f"دائرة {a.parent.name_ar.replace('دائرة خدمات ', '')}" if a.parent else "دمشق"
        neighborhoods.append({
            "type": "neighborhood",
            "id": a.id,
            "title": a.name_ar,
            "subtitle": f"حي سكني • {parent_title}",
            "code": a.code,
            "level": 10,
            "icon": "home",
            "color": "#3a6962",
            "coordinates": coords,
            "boundary": a.boundary,
        })
    # 3. الشوارع والمحاور الرئيسية (Streets)
    q_street = Q()
    for v in variants:
        q_street |= Q(search_text__icontains=v)
    q_street |= Q(name_en__icontains=query)

    streets = []
    street_qs = Street.objects.filter(is_active=True).filter(q_street).select_related('admin_area')[:30]
    for s in street_qs:
        hw_label = HIGHWAY_LABELS.get(s.highway_type, "شارع")
        neigh_label = s.admin_area.name_ar if s.admin_area else "دمشق"
        streets.append({
            "type": "street",
            "id": s.id,
            "title": s.name_ar,
            "subtitle": f"{hw_label} • {neigh_label}",
            "highway_type": s.highway_type,
            "icon": "route",
            "color": "#4f46e5",
            "coordinates": [s.center_lon, s.center_lat],
            "bbox": s.bbox,
            "geometry": s.geometry,
        })

    # 4. الأماكن والمنشآت (Places)
    q_places = Q()
    for v in variants:
        q_places |= Q(search_text__icontains=v)
    q_places |= Q(title_en__icontains=query)

    places_qs = Place.objects.filter(is_visible=True, latitude__isnull=False, longitude__isnull=False).filter(q_places).select_related('sub_category__category', 'admin_area')
    if category_slug:
        places_qs = places_qs.filter(sub_category__category__slug=category_slug)

    places = []
    for p in places_qs[:35]:
        places.append({
            "type": "place",
            "id": p.id,
            "title": p.title,
            "subtitle": f"{p.category.name_ar if p.category else ''} • {p.admin_area.name_ar if p.admin_area else 'دمشق'}",
            "icon": p.category.icon if p.category else "map-pin",
            "color": p.category.color if p.category else "#064239",
            "coordinates": [p.longitude, p.latitude],
            "category_slug": p.category.slug if p.category else "",
        })

    # 5. خطوط النقل (Bus Lines)
    q_bus = Q()
    for v in variants:
        q_bus |= Q(name__icontains=v)

    buses = []
    for b in Bus.objects.filter(is_active=True).filter(q_bus)[:10]:
        buses.append({
            "type": "bus",
            "id": b.id,
            "title": f"خط سرفيس: {b.name}",
            "subtitle": f"رمز الخط: {b.code or 'دمشق'}",
            "icon": "bus",
            "color": b.color or "#3a6962",
            "coordinates": [36.295, 33.513],
        })

    # التجميع الذكي مع احتساب نقاط المطابقة (Relevance Scoring & Deduplication)
    def compute_score(item):
        norm_title = normalize_arabic(item.get("title", ""))
        score = 0
        if norm_title == norm_query:
            score += 150
        elif any(norm_title == v for v in variants):
            score += 120
        elif norm_title.startswith(norm_query) or any(norm_title.startswith(v) for v in variants):
            score += 80
        elif any(v in norm_title for v in variants):
            score += 50
        else:
            score += 10
        # تعزيز التقسيمات والشوارع عند التطابق
        if item.get("type") == "municipality":
            score += 25
        elif item.get("type") == "neighborhood":
            score += 20
        elif item.get("type") == "street":
            score += 15
        return score

    municipalities.sort(key=compute_score, reverse=True)
    neighborhoods.sort(key=compute_score, reverse=True)
    streets.sort(key=compute_score, reverse=True)
    places.sort(key=compute_score, reverse=True)
    buses.sort(key=compute_score, reverse=True)

    grouped = {
        "municipalities": municipalities[:6],
        "neighborhoods": neighborhoods[:8],
        "streets": streets[:8],
        "places": places[:10],
        "buses": buses[:4],
    }

    all_raw = grouped["municipalities"] + grouped["neighborhoods"] + grouped["streets"] + grouped["places"] + grouped["buses"]
    all_raw.sort(key=compute_score, reverse=True)

    seen_keys = set()
    combined = []
    for item in all_raw:
        key = (item["type"], item["id"])
        if key not in seen_keys:
            seen_keys.add(key)
            combined.append(item)

    grouped = {
        "municipalities": municipalities,
        "neighborhoods": neighborhoods,
        "streets": streets,
        "places": places,
        "buses": buses,
    }
    counts = {
        "all": len(combined),
        "municipalities": len(municipalities),
        "neighborhoods": len(neighborhoods),
        "streets": len(streets),
        "places": len(places),
        "buses": len(buses),
    }

    return JsonResponse({
        "query": query,
        "count": len(combined),
        "results": combined,
        "grouped": grouped,
        "counts": counts,
    })


@require_GET
def list_transit_lines(request):
    """
    قائمة خطوط باصات وسرافيس دمشق ومساراتها ومحطاتها المعتمدة
    """
    lines = Bus.objects.filter(is_active=True).prefetch_related('routes')
    results = []
    for line in lines:
        active = sorted((route for route in line.routes.all() if route.is_active),
                        key=lambda route: (route.direction != 'outbound', route.id))
        if not active:
            continue
        route = active[0]
        coords = route.geometry.get('coordinates', [])
        if not coords:
            continue
        start = {'name': route.start_point, 'coordinates': coords[0]}
        end = {'name': route.end_point, 'coordinates': coords[-1]}
        results.append({
            'id': line.id, 'name': line.name, 'name_en': '', 'code': line.code,
            'color': line.color, 'group_id': str(line.id), 'group_title': line.name,
            'corridor': '', 'corridor_slug': '', 'direction': route.direction,
            'direction_name': route.get_direction_display(),
            'start_terminal': start, 'destination_terminal': end,
            'stops': [dict(start, id=1, is_start=True), dict(end, id=2, is_destination=True)],
            'stops_count': 2, 'cost': float(route.cost), 'length_km': route.route_length_km,
            'trip_time_mins': route.trip_time, 'geometry': route.geometry,
            'routes': [{'route_id': item.id, 'direction': item.direction,
                        'direction_name': item.get_direction_display(),
                        'geometry': item.geometry,
                        'start_terminal': {'name': item.start_point, 'coordinates': item.geometry['coordinates'][0]},
                        'destination_terminal': {'name': item.end_point, 'coordinates': item.geometry['coordinates'][-1]},
                        'stops': [
                            {'id': 1, 'name': item.start_point, 'coordinates': item.geometry['coordinates'][0], 'is_start': True},
                            {'id': 2, 'name': item.end_point, 'coordinates': item.geometry['coordinates'][-1], 'is_destination': True},
                        ],
                        'cost': float(item.cost), 'length_km': item.route_length_km,
                        'trip_time_mins': item.trip_time} for item in active if item.geometry.get('coordinates')],
        })
    return JsonResponse({'count': len(results), 'results': results})


@require_GET
def list_all_transit_routes_geojson(request):
    """
    إرجاع كافة مسارات شبكة باصات وسرافيس دمشق بصيغة GeoJSON FeatureCollection واحدة
    لتتمكن خريطة MapLibre من عرضها كطبقة خطوط متجهة متكاملة وسريعة
    """
    routes = BusRoute.objects.filter(is_active=True, bus_line__is_active=True).select_related('bus_line')
    features = []
    for r in routes:
        spec = getattr(r, 'specifications', None)
        features.append({
            "type": "Feature",
            "id": r.id,
            "properties": {
                "route_id": r.id,
                "line_id": r.bus_line.id,
                "line_name": r.bus_line.name,
                "line_code": r.bus_line.code,
                "direction": r.direction,
                "color": r.bus_line.color or "#064239",
                "cost": float(spec.cost) if spec else 500,
                "length_km": spec.route_length_km if spec else 0,
                "trip_time_mins": spec.trip_time_minutes if spec else 0,
            },
            "geometry": r.geometry,
        })

    return JsonResponse({
        "type": "FeatureCollection",
        "count": len(features),
        "features": features,
    })



@require_GET
def get_transit_route_geojson(request, route_id):
    """
    إرجاع المسار الجغرافي لخط باص محدد بصيغة GeoJSON
    """
    try:
        route = BusRoute.objects.select_related('bus_line').get(id=route_id)
    except BusRoute.DoesNotExist:
        raise Http404("مسار الخط غير موجود")

    spec = getattr(route, 'specifications', None)

    feature = {
        "type": "Feature",
        "id": route.id,
        "properties": {
            "route_id": route.id,
            "line_id": route.bus_line.id,
            "line_name": route.bus_line.name,
            "direction": route.direction,
            "color": route.bus_line.color,
            "cost": float(spec.cost) if spec else 500,
            "length_km": spec.route_length_km if spec else 0,
            "trip_time_mins": spec.trip_time_minutes if spec else 0,
        },
        "geometry": route.geometry,
    }

    return JsonResponse(feature)


@require_GET
def calculate_route(request):
    """
    محرك التوجيه وحساب الوصول إلى المكان (Step 5):
    الأنماط المدعومة:
    - transit: المواصلات العامة (الباصات والسرافيس مع المواقف والتعرفة والزمن)
    - car: السيارة (طريق سريع/رئيسي في دمشق مع مسافة ووقت)
    - walk: مشياً على الأقدام (مسار المشي مع حرق السعرات والوقت)
    البارامترات:
    start_lat, start_lon, end_lat, end_lon, mode
    """
    try:
        start_lat = float(request.GET.get('start_lat'))
        start_lon = float(request.GET.get('start_lon'))
        end_lat = float(request.GET.get('end_lat'))
        end_lon = float(request.GET.get('end_lon'))
    except (TypeError, ValueError):
        return JsonResponse({"error": "يرجى تزويد إحداثيات البداية والنهاية بشكل صحيح"}, status=400)

    mode = request.GET.get('mode', 'transit').lower()
    total_straight_dist_km = haversine_distance_km(start_lat, start_lon, end_lat, end_lon)

    # 1. وضع المواصلات العامة (Transit)
    if mode == 'transit':
        # البحث عن أقرب مسار باص من نقطة الانطلاق
        all_routes = BusRoute.objects.filter(is_active=True, bus_line__is_active=True).select_related('bus_line')
        best_route = None
        min_combined_dist = 999999.0

        for r in all_routes:
            coords = r.geometry.get('coordinates', [])
            if not coords:
                continue
            # تقريب المسافة من البداية والنهاية للمسار
            d_start = min(haversine_distance_km(start_lat, start_lon, pt[1], pt[0]) for pt in coords[:min(len(coords), 30)])
            d_end = min(haversine_distance_km(end_lat, end_lon, pt[1], pt[0]) for pt in coords[max(0, len(coords)-30):])
            comb = d_start + d_end
            if comb < min_combined_dist:
                min_combined_dist = comb
                best_route = r

        if best_route and min_combined_dist < 6.0:
            spec = getattr(best_route, 'specifications', None)
            route_coords = best_route.geometry.get('coordinates', [])
            full_path = [[start_lon, start_lat]] + route_coords + [[end_lon, end_lat]]
            trip_km = round(total_straight_dist_km * 1.35, 2)
            duration_mins = max(12, int(trip_km * 3.2))

            return JsonResponse({
                "mode": "transit",
                "mode_title": "مواصلات عامة (باص / سرفيس)",
                "summary": f"باص {best_route.bus_line.name}",
                "line_name": best_route.bus_line.name,
                "cost_syp": float(spec.cost) if spec else 500,
                "total_distance_km": trip_km,
                "duration_minutes": duration_mins,
                "steps": [
                    {
                        "instruction": f"سر مشياً مسافة {int(min_combined_dist * 400)}م إلى أقرب محطة صعود لسرفيس {best_route.bus_line.name}",
                        "icon": "walk",
                        "duration_mins": 4,
                    },
                    {
                        "instruction": f"اصعد سرفيس {best_route.bus_line.name} (التعرفة الرسمية: {int(spec.cost if spec else 500)} ل.س)",
                        "icon": "bus",
                        "duration_mins": duration_mins - 7,
                    },
                    {
                        "instruction": "انزل عند الموقف الأقرب لوجهتك، ثم سر دقيقتين للوصول للموقع",
                        "icon": "map-pin",
                        "duration_mins": 3,
                    }
                ],
                "route_geojson": {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": full_path,
                    },
                    "properties": {
                        "color": "#064239",
                        "mode": "transit",
                    }
                }
            })

    # 2. وضع قيادة السيارة (Car)
    if mode == 'car':
        driving_km = round(total_straight_dist_km * 1.25, 2)
        duration_mins = max(4, int(driving_km * 2.1)) # متوسط 30 كم/س داخل شوارع دمشق

        # توليد نقاط المسار التوجيهي
        mid_lon = (start_lon + end_lon) / 2 + 0.001
        mid_lat = (start_lat + end_lat) / 2 - 0.0008
        car_path = [
            [start_lon, start_lat],
            [(start_lon + mid_lon)/2, (start_lat + mid_lat)/2],
            [mid_lon, mid_lat],
            [(mid_lon + end_lon)/2, (mid_lat + end_lat)/2],
            [end_lon, end_lat]
        ]

        return JsonResponse({
            "mode": "car",
            "mode_title": "بالسيارة",
            "summary": "عبر الشوارع الرئيسية والمحاور الحيوية",
            "cost_syp": 0,
            "total_distance_km": driving_km,
            "duration_minutes": duration_mins,
            "steps": [
                {
                    "instruction": "انطلق باتجاه الشارع الرئيسي الأقرب",
                    "icon": "car",
                    "duration_mins": 2,
                },
                {
                    "instruction": f"تابع على المسار مسافة {driving_km} كم نحو الوجهة",
                    "icon": "arrow-up",
                    "duration_mins": duration_mins - 3,
                },
                {
                    "instruction": "انعطف نحو المدخل وتصل إلى وجهتك على اليمين",
                    "icon": "map-pin",
                    "duration_mins": 1,
                }
            ],
            "route_geojson": {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": car_path,
                },
                "properties": {
                    "color": "#c8a76a",
                    "mode": "car",
                }
            }
        })

    # 3. وضع المشي على الأقدام (Walk)
    walk_km = round(total_straight_dist_km * 1.15, 2)
    duration_mins = max(3, int(walk_km * 13.5)) # مشي 4.5 كم/س
    calories = int(walk_km * 55)

    walk_path = [
        [start_lon, start_lat],
        [(start_lon * 2 + end_lon) / 3, (start_lat * 2 + end_lat) / 3],
        [(start_lon + end_lon * 2) / 3, (start_lat + end_lat * 2) / 3],
        [end_lon, end_lat]
    ]

    return JsonResponse({
        "mode": "walk",
        "mode_title": "مشياً على الأقدام",
        "summary": "مسار مشي آمن عبر الأرصفة والممرات المخصصة",
        "cost_syp": 0,
        "total_distance_km": walk_km,
        "duration_minutes": duration_mins,
        "calories_burned": calories,
        "steps": [
            {
                "instruction": "ابدأ المشي عبر الرصيف بمحاذاة الشارع",
                "icon": "walk",
                "duration_mins": 2,
            },
            {
                "instruction": f"واصل السير بشكل مستقيم مسافة {walk_km} كم",
                "icon": "arrow-up",
                "duration_mins": duration_mins - 2,
            },
            {
                "instruction": "الوصول إلى الوجهة المقصودة",
                "icon": "map-pin",
                "duration_mins": 1,
            }
        ],
        "route_geojson": {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": walk_path,
            },
            "properties": {
                "color": "#3a6962",
                "mode": "walk",
            }
        }
    })


@require_GET
def list_notifications(request):
    """
    إرجاع تنبيهات وإشعارات الخريطة الفعالة
    """
    notifs = Notification.objects.filter(is_active=True)[:10]
    results = [
        {
            "id": n.id,
            "content": n.content,
            "urgency": n.urgency,
            "start_date": n.start_date.strftime("%Y-%m-%d %H:%M"),
            "coordinates": [n.longitude, n.latitude] if n.latitude and n.longitude else None,
        }
        for n in notifs
    ]
    return JsonResponse({"results": results})
