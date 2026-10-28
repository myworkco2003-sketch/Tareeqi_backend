
import json
import os
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from django.db import transaction, IntegrityError
from django.db.models import Max
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from places.models import Bus, BusRoute
from django.db import transaction

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def error_response(message, status=400):
    return JsonResponse({"detail": message}, status=status)


def read_json_body(request):
    try:
        body = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("JSON المرسل غير صالح")

    if not isinstance(body, dict):
        raise ValueError("يجب أن يكون جسم الطلب JSON object")

    return body


def validate_bus_fields(body, creating=False):
    data = {}

    if creating or "name" in body:
        name = body.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("اسم الباص مطلوب")
        name = name.strip()
        if len(name) > 150:
            raise ValueError("اسم الباص يجب ألا يتجاوز 150 حرفاً")
        data["name"] = name

    if creating or "color" in body:
        color = body.get("color", "#3a6962")
        if not isinstance(color, str) or not re.fullmatch(
            r"#[0-9A-Fa-f]{6}", color
        ):
            raise ValueError("لون الباص يجب أن يكون بصيغة #RRGGBB")
        data["color"] = color

    # التوافق مع API القديمة التي تستخدم price،
    # ومع الموديل الحالي الذي يحتوي old_price وnew_price.
    if "price" in body:
        data["new_price"] = validate_price(body["price"])

    if "old_price" in body:
        data["old_price"] = validate_price(body["old_price"])

    if "new_price" in body:
        data["new_price"] = validate_price(body["new_price"])

    return data


def validate_price(value):
    if value is None or value == "":
        return None

    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("السعر يجب أن يكون رقماً صالحاً")

    if not price.is_finite() or price < 0:
        raise ValueError("السعر يجب أن يكون رقماً موجباً أو صفراً")

    if price.as_tuple().exponent < -2:
        raise ValueError("السعر يقبل منزلتين عشريتين كحد أقصى")

    if price > Decimal("99999999.99"):
        raise ValueError("السعر أكبر من الحد المسموح")

    return price


def validate_direction(value):
    mapping = {
        "ذهاب": "outbound",
        "إياب": "inbound",
        "outbound": "outbound",
        "inbound": "inbound",
    }

    if value not in mapping:
        raise ValueError("الاتجاه يجب أن يكون ذهاب أو إياب")

    return mapping[value]


def validate_endpoint(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} مطلوب")

    value = value.strip()
    if len(value) > 150:
        raise ValueError(f"{field_name} يجب ألا يتجاوز 150 حرفاً")

    return value


def route_to_dict(route, include_geometry=False):
    bus = route.bus

    data = {
        "id": route.id,
        "bus_id": route.bus_id,
        "route_name": bus.name,
        "name": bus.name,
        "color": bus.color,
        "old_price": (
            float(bus.old_price) if bus.old_price is not None else None
        ),
        "new_price": (
            float(bus.new_price) if bus.new_price is not None else None
        ),
        "fare": (
            float(bus.new_price) if bus.new_price is not None else None
        ),
        "direction": "ذهاب" if route.direction == "outbound" else "إياب",
        "version": route.version,
        "start_point": route.start_point,
        "end_point": route.end_point,
        "distance_m": route.distance,
        "trip_time_s": route.trip_time * 60,
        "is_active": route.is_active,
    }

    if include_geometry:
        data["geometry"] = route.geometry

    return data


def get_route_waypoints(body):
    waypoints = body.get("waypoints")

    if not isinstance(waypoints, list) or len(waypoints) < 2:
        raise ValueError("يجب إرسال نقطتين على الأقل ضمن waypoints")

    return waypoints


# ---------------------------------------------------------
# BRouter
# ---------------------------------------------------------

def calculate_geometry(waypoints):
    if not isinstance(waypoints, list) or len(waypoints) < 2:
        raise ValueError("يجب إرسال نقطتين على الأقل")

    pairs = []

    for point in waypoints:
        if not isinstance(point, dict):
            raise ValueError("صيغة نقطة المسار غير صحيحة")

        try:
            lon = float(point["lon"])
            lat = float(point["lat"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("كل نقطة يجب أن تحتوي على lon و lat")

        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("إحداثيات النقطة خارج النطاق المسموح")

        pairs.append(f"{lon},{lat}")

    base_url = os.environ.get(
        "BROUTER_URL", "http://localhost:17777"
    ).rstrip("/")

    params = urlencode({
        "lonlats": "|".join(pairs),
        "profile": "car-eco",
        "alternativeidx": 0,
        "format": "geojson",
    })

    req = Request(
        f"{base_url}/brouter?{params}",
        headers={"Accept": "application/json"},
        method="GET",
    )

    try:
        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("تعذّر الاتصال بخدمة BRouter") from exc

    features = result.get("features") or []
    if not features:
        raise RuntimeError("لم تُرجع خدمة BRouter أي مسار")

    feature = features[0]
    geometry = feature.get("geometry")
    properties = feature.get("properties") or {}

    if (
        not isinstance(geometry, dict)
        or geometry.get("type") != "LineString"
        or not isinstance(geometry.get("coordinates"), list)
        or len(geometry["coordinates"]) < 2
    ):
        raise RuntimeError("الهندسة التي أعادها BRouter غير صالحة")

    try:
        distance_m = float(properties["track-length"])
        duration_s = float(properties["total-time"])
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("استجابة BRouter لا تحتوي على المسافة والمدة")

    if (
        not all(map(lambda n: n >= 0 and n < float("inf"), [
            distance_m, duration_s
        ]))
    ):
        raise RuntimeError("المسافة أو المدة التي أعادها BRouter غير صالحة")

    return geometry, distance_m, duration_s


def save_route(bus, direction, start_point, end_point,
               geometry, distance_m, duration_s, version):
    """
    يحفظ مدة الرحلة بالدقائق، لأن BusRoute.trip_time مخزن بالدقائق.
    """
    return BusRoute.objects.create(
        bus=bus,
        version=version,
        geometry=geometry,
        distance=distance_m,
        trip_time=max(0, round(duration_s / 60)),
        direction=direction,
        start_point=start_point,
        end_point=end_point,
        is_active=True,
    )


# ---------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------

@require_GET
def routes_list(request):
    routes = (
        BusRoute.objects
        .filter(is_active=True, bus__is_active=True)
        .select_related("bus")
        .order_by("bus__name", "direction")
    )

    return JsonResponse(
        [route_to_dict(route) for route in routes],
        safe=False,
    )


@require_GET
def routes_map(request):
    routes = (
        BusRoute.objects
        .filter(is_active=True, bus__is_active=True)
        .select_related("bus")
        .order_by("bus__name", "direction")
    )

    return JsonResponse(
        [route_to_dict(route, include_geometry=True) for route in routes],
        safe=False,
    )



@require_GET
def admin_routes_list(request):
    # المسارات النشطة للباصات النشطة: كل مسار يظهر كسجل مستقل.
    active_routes = (
        BusRoute.objects
        .filter(is_active=True, bus__is_active=True)
        .select_related("bus")
        .order_by("bus__name", "direction")
    )

    # الباصات غير النشطة بالكامل: نعرض سجلاً واحداً لكل باص،
    # حتى لو كان لديه عدة مسارات أو إصدارات قديمة.
    inactive_buses = (
        Bus.objects
        .filter(is_active=False)
        .order_by("name")
    )

    result = [route_to_dict(route) for route in active_routes]

    # نضيف الباص غير النشط مرة واحدة فقط.
    for bus in inactive_buses:
        last_route = (
            BusRoute.objects
            .filter(bus=bus)
            .order_by("-version", "-id")
            .first()
        )

        if last_route:
            item = route_to_dict(last_route)
            item["is_active"] = False
            result.append(item)

        else:
            # احتياطياً، إذا كان الباص لا يملك أي مسار.
            result.append({
                "id": None,
                "bus_id": bus.id,
                "route_name": bus.name,
                "name": bus.name,
                "color": bus.color,
                "old_price": (
                    float(bus.old_price)
                    if bus.old_price is not None else None
                ),
                "new_price": (
                    float(bus.new_price)
                    if bus.new_price is not None else None
                ),
                "fare": (
                    float(bus.new_price)
                    if bus.new_price is not None else None
                ),
                "direction": None,
                "version": None,
                "start_point": None,
                "end_point": None,
                "distance_m": None,
                "trip_time_s": None,
                "is_active": False,
            })

    return JsonResponse(result, safe=False)


# ---------------------------------------------------------
# Preview
# ---------------------------------------------------------

@csrf_exempt
@require_POST
def preview_route(request):
    try:
        body = read_json_body(request)
        geometry, distance_m, duration_s = calculate_geometry(
            get_route_waypoints(body)
        )
    except ValueError as exc:
        return error_response(str(exc), 422)
    except RuntimeError as exc:
        return error_response(str(exc), 502)

    return JsonResponse({
        "geometry": geometry,
        "distance_m": distance_m,
        "trip_time_s": int(duration_s),
        "duration_seconds": int(duration_s),
        "duration_minutes": duration_s / 60,
    })


# ---------------------------------------------------------
# Create bus + first route
# POST /api/admin/routes
# ---------------------------------------------------------

@csrf_exempt
def routes_collection(request):
    if request.method == "GET":
        return routes_list(request)

    if request.method == "POST":
        return create_bus_with_route(request)

    return error_response("Method not allowed", 405)


@csrf_exempt
@require_POST
def create_bus_with_route(request):
    try:
        body = read_json_body(request)
        bus_data = validate_bus_fields(body, creating=True)
        direction = validate_direction(body.get("direction"))
        start_point = validate_endpoint(body.get("start_point"), "نقطة البداية")
        end_point = validate_endpoint(body.get("end_point"), "نقطة النهاية")
        waypoints = get_route_waypoints(body)

        geometry, distance_m, duration_s = calculate_geometry(waypoints)

    except ValueError as exc:
        return error_response(str(exc), 422)
    except RuntimeError as exc:
        return error_response(str(exc), 502)

    try:
        with transaction.atomic():
            if Bus.objects.filter(name=bus_data["name"]).exists():
                return error_response("اسم الباص مستخدم مسبقاً", 409)

            bus = Bus.objects.create(**bus_data)

            route = save_route(
                bus=bus,
                direction=direction,
                start_point=start_point,
                end_point=end_point,
                geometry=geometry,
                distance_m=distance_m,
                duration_s=duration_s,
                version=1,
            )

    except IntegrityError:
        return error_response("تعذّر حفظ الباص أو المسار بسبب تعارض بالبيانات", 409)

    return JsonResponse({
        "message": "تم إنشاء الباص والمسار بنجاح",
        "bus": {
            "id": bus.id,
            "name": bus.name,
            "color": bus.color,
            "old_price": float(bus.old_price) if bus.old_price is not None else None,
            "new_price": float(bus.new_price) if bus.new_price is not None else None,
            "is_active": bus.is_active,
        },
        "route": route_to_dict(route, include_geometry=True),
    }, status=201)


# ---------------------------------------------------------
# Add the other direction
# POST /api/admin/routes/buses/<bus_id>/routes
# ---------------------------------------------------------

@csrf_exempt
@require_POST
def add_direction(request, bus_id):
    try:
        body = read_json_body(request)
        direction = validate_direction(body.get("direction"))
        start_point = validate_endpoint(body.get("start_point"), "نقطة البداية")
        end_point = validate_endpoint(body.get("end_point"), "نقطة النهاية")
        waypoints = get_route_waypoints(body)

        geometry, distance_m, duration_s = calculate_geometry(waypoints)

    except ValueError as exc:
        return error_response(str(exc), 422)
    except RuntimeError as exc:
        return error_response(str(exc), 502)

    try:
        with transaction.atomic():
            bus = Bus.objects.select_for_update().get(
                pk=bus_id, is_active=True
            )

            if BusRoute.objects.filter(
                bus=bus, direction=direction, is_active=True
            ).exists():
                return error_response(
                    "يوجد مسار نشط لهذا الاتجاه مسبقاً", 409
                )

            latest_version = (
                BusRoute.objects
                .filter(bus=bus, direction=direction)
                .aggregate(max_version=Max("version"))["max_version"]
                or 0
            )

            route = save_route(
                bus=bus,
                direction=direction,
                start_point=start_point,
                end_point=end_point,
                geometry=geometry,
                distance_m=distance_m,
                duration_s=duration_s,
                version=latest_version + 1,
            )

    except Bus.DoesNotExist:
        return error_response("الباص غير موجود أو غير نشط", 404)
    except IntegrityError:
        return error_response("حدث تعارض أثناء حفظ الاتجاه", 409)

    return JsonResponse({
        "message": "تمت إضافة الاتجاه بنجاح",
        "route": route_to_dict(route, include_geometry=True),
    }, status=201)


# ---------------------------------------------------------
# Update route by creating a new version
# PUT /api/admin/routes/<route_id>
# ---------------------------------------------------------

@csrf_exempt
def route_detail(request, route_id):
    if request.method == "DELETE":
        return deactivate_route(request, route_id)

    if request.method != "PUT":
        return error_response("Method not allowed", 405)

    try:
        body = read_json_body(request)

        # direction is deliberately not editable on an existing route.
        # if "direction" in body:
        #     raise ValueError(
        #         "لا يمكن تغيير اتجاه المسار؛ أنشئ مساراً جديداً للاتجاه الآخر"
        #     )

        bus_updates = validate_bus_fields(body, creating=False)

        start_point = None
        end_point = None
        geometry = None
        distance_m = None
        duration_s = None

        has_route_changes = any(
            key in body for key in ("start_point", "end_point", "waypoints")
        )

        if has_route_changes:
            start_point = validate_endpoint(
                body.get("start_point"), "نقطة البداية"
            )
            end_point = validate_endpoint(
                body.get("end_point"), "نقطة النهاية"
            )
            waypoints = get_route_waypoints(body)
            geometry, distance_m, duration_s = calculate_geometry(waypoints)

    except ValueError as exc:
        return error_response(str(exc), 422)
    except RuntimeError as exc:
        return error_response(str(exc), 502)

    try:
        with transaction.atomic():
            old_route = (
                BusRoute.objects
                .select_for_update()
                .select_related("bus")
                .get(pk=route_id, is_active=True, bus__is_active=True)
            )

            DIRECTION_MAP = {
                "ذهاب": "outbound",
                "إياب": "inbound",
                "outbound": "outbound",
                "inbound": "inbound",
            }

            if "direction" in body:
                requested_direction = DIRECTION_MAP.get(body["direction"])

                if requested_direction is None:
                    return error_response("اتجاه المسار غير صالح", 422)

                if requested_direction != old_route.direction:
                    return error_response(
                        "لا يمكن تغيير اتجاه المسار؛ أنشئ مساراً جديداً للاتجاه الآخر",
                        422,
                    )

            bus = Bus.objects.select_for_update().get(pk=old_route.bus_id)

            if "name" in bus_updates and Bus.objects.filter(
                name=bus_updates["name"]
            ).exclude(pk=bus.pk).exists():
                return error_response("اسم الباص مستخدم مسبقاً", 409)

            if bus_updates:
                for field, value in bus_updates.items():
                    setattr(bus, field, value)
                bus.save(update_fields=list(bus_updates.keys()))

            if has_route_changes:
                latest_version = (
                    BusRoute.objects
                    .filter(
                        bus=bus,
                        direction=old_route.direction,
                    )
                    .aggregate(max_version=Max("version"))["max_version"]
                    or old_route.version
                )

                old_route.is_active = False
                old_route.save(update_fields=["is_active"])

                new_route = save_route(
                    bus=bus,
                    direction=old_route.direction,
                    start_point=start_point,
                    end_point=end_point,
                    geometry=geometry,
                    distance_m=distance_m,
                    duration_s=duration_s,
                    version=latest_version + 1,
                )
            else:
                # إذا التغيير على اسم الباص أو اللون أو السعر فقط،
                # لا داعي لإنشاء إصدار مسار جديد.
                new_route = old_route

    except BusRoute.DoesNotExist:
        return error_response("المسار غير موجود أو غير نشط", 404)
    except Bus.DoesNotExist:
        return error_response("الباص غير موجود", 404)
    except IntegrityError:
        return error_response("حدث تعارض أثناء تحديث المسار", 409)

    return JsonResponse({
        "message": "تم التحديث بنجاح",
        "route": route_to_dict(new_route, include_geometry=True),
    })


# ---------------------------------------------------------
# Soft deactivate route
# DELETE /api/admin/routes/<route_id>
# ---------------------------------------------------------


@csrf_exempt
def deactivate_route(request, route_id):
    if request.method != "DELETE":
        return error_response("Method not allowed", 405)

    try:
        with transaction.atomic():
            route = (
                BusRoute.objects
                .select_for_update()
                .select_related("bus")
                .filter(pk=route_id, is_active=True)
                .first()
            )

            if route is None:
                return error_response(
                    "المسار غير موجود أو غير نشط",
                    404,
                )

            bus = Bus.objects.select_for_update().get(
                pk=route.bus_id
            )

            route.is_active = False
            route.save(update_fields=["is_active"])

            # هل بقي أي مسار نشط لهذا الباص؟
            has_active_routes = BusRoute.objects.filter(
                bus_id=bus.pk,
                is_active=True,
            ).exists()

            # إذا لم يبقَ أي مسار نشط، نعطّل الباص أيضاً.
            if not has_active_routes and bus.is_active:
                bus.is_active = False
                bus.save(update_fields=["is_active"])

    except Bus.DoesNotExist:
        return error_response("الباص غير موجود", 404)

    return JsonResponse({
        "message": "تم تعطيل المسار بنجاح",
        "route_id": route_id,
        "is_active": False,
        "bus_id": bus.pk,
        "bus_is_active": bus.is_active,
    })


# ---------------------------------------------------------
# Soft deactivate bus and all its active routes
# DELETE /api/admin/routes/buses/<bus_id>
# ---------------------------------------------------------

@csrf_exempt
def deactivate_bus(request, bus_id):
    if request.method != "DELETE":
        return error_response("Method not allowed", 405)

    try:
        with transaction.atomic():
            bus = Bus.objects.select_for_update().get(
                pk=bus_id, is_active=True
            )

            BusRoute.objects.filter(
                bus=bus, is_active=True
            ).update(is_active=False)

            bus.is_active = False
            bus.save(update_fields=["is_active"])

    except Bus.DoesNotExist:
        return error_response("الباص غير موجود أو غير نشط", 404)

    return JsonResponse({
        "message": "تم تعطيل الباص ومساراته بنجاح",
        "bus_id": bus_id,
        "is_active": False,
    })
