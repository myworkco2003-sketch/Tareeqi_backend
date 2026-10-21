from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.elements import WKTElement
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import BRouterWaypointsRequest, RoutePreviewRequest, RouteSaveRequest
from app.db.database import get_db
from app.db.models import Bus, BusRoute
from app.services.brouter_service import calculate_route

router = APIRouter(prefix="/admin/routes", tags=["Admin Routes"])


def _now():
    return datetime.now(timezone.utc)


def _to_wkt(geometry: dict) -> str:
    coordinates = geometry["coordinates"]
    if len(coordinates) < 2:
        raise HTTPException(status_code=422, detail="LineString must contain at least two points")
    return "LINESTRING(" + ", ".join(
        f"{float(point[0])} {float(point[1])}" for point in coordinates
    ) + ")"


def _point_wkt(point: dict | None, fallback: list[float]) -> str:
    lon = float(point["lon"]) if point else float(fallback[0])
    lat = float(point["lat"]) if point else float(fallback[1])
    return f"POINT({lon} {lat})"


def _route_geometry(db: Session, route_id: int):
    return db.execute(
        text('SELECT ST_AsGeoJSON("lineString")::json FROM public.bus_route WHERE "uniqueID" = :id'),
        {"id": route_id},
    ).scalar()


def _route_payload(db: Session, route: BusRoute, bus: Bus):
    geometry = _route_geometry(db, route.uniqueID)
    return {
        "id": route.uniqueID,
        "route_id": route.uniqueID,
        "bus_id": bus.uniqueID,
        "route_name": bus.name,  # backwards compatibility with current dashboard
        "name": bus.name,
        "color": bus.color,
        "fare": float(bus.newPrice) if bus.newPrice is not None else None,
        "old_price": float(bus.oldPrice) if bus.oldPrice is not None else None,
        "new_price": float(bus.newPrice) if bus.newPrice is not None else None,
        "version": route.version,
        "direction": route.direction,
        "distance_m": float(route.distance) if route.distance is not None else None,
        "duration_minutes": float(route.tripTime) if route.tripTime is not None else None,
        "trip_time": route.tripTime,
        "is_active": route.isActive,
        "geometry": geometry,
    }


def _bump_dataset_version(db: Session):
    # Older deployments use this singleton to notify the mobile app about changes.
    db.execute(text(
        "UPDATE dataset_version SET version = version + 1, updated_at = now() WHERE id = 1"
    ))


def _save_route(request: RouteSaveRequest, db: Session, existing_route_id: int | None = None):
    now = _now()
    name = (request.name or request.route_name or "").strip()
    color = request.color
    new_price = request.new_price if request.new_price is not None else request.fare

    if not name:
        raise HTTPException(status_code=422, detail="اسم الباص مطلوب")
    if new_price is None:
        raise HTTPException(status_code=422, detail="السعر الجديد مطلوب")

    current_route = None
    if existing_route_id is not None:
        current_route = (
            db.query(BusRoute)
            .filter(BusRoute.uniqueID == existing_route_id)
            .with_for_update()
            .first()
        )
        if current_route is None:
            raise HTTPException(status_code=404, detail="Route not found")
        bus = (
            db.query(Bus)
            .filter(Bus.uniqueID == current_route.busID)
            .with_for_update()
            .first()
        )
        if bus is None:
            raise HTTPException(status_code=404, detail="Bus not found")
        if request.bus_id is not None and request.bus_id != bus.uniqueID:
            raise HTTPException(status_code=422, detail="bus_id cannot change when editing a route")
    elif request.bus_id is not None:
        bus = (
            db.query(Bus)
            .filter(Bus.uniqueID == request.bus_id)
            .with_for_update()
            .first()
        )
        if bus is None:
            raise HTTPException(status_code=404, detail="Bus not found")
    else:
        bus = Bus(name=name, color=color, oldPrice=request.old_price, newPrice=new_price,
                  isActive=request.is_active)
        db.add(bus)
        db.flush()

    bus.name = name
    if color is not None:
        bus.color = color
    if request.old_price is not None:
        bus.oldPrice = request.old_price
    bus.newPrice = new_price
    bus.isActive = request.is_active

    # A database-level advisory lock serializes version creation for this bus/direction.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": f"bus-route:{bus.uniqueID}:{request.direction}"},
    )

    if current_route is not None:
        same_group = (
            current_route.busID == bus.uniqueID
            and current_route.direction == request.direction
        )
    else:
        same_group = False

    latest = (
        db.query(BusRoute)
        .filter(
            BusRoute.busID == bus.uniqueID,
            BusRoute.direction == request.direction,
        )
        .order_by(BusRoute.version.desc())
        .with_for_update()
        .first()
    )

    geometry_wkt = _to_wkt(request.geometry)
    coordinates = request.geometry["coordinates"]
    start_point = _point_wkt(request.start_point.model_dump() if request.start_point else None, coordinates[0])
    end_point = _point_wkt(request.end_point.model_dump() if request.end_point else None, coordinates[-1])

    # If geometry is identical, update metadata on the latest version instead of
    # creating a new version. Geometry changes create a new historical row.
    if latest is not None:
        is_same_geometry = db.execute(
            text("""
                SELECT ST_AsEWKB("lineString") = ST_AsEWKB(ST_GeomFromText(:wkt, 4326))
                FROM public.bus_route
                WHERE "uniqueID" = :route_id
            """),
            {"wkt": geometry_wkt, "route_id": latest.uniqueID},
        ).scalar()

        if is_same_geometry:
            latest.distance = request.distance_m if request.distance_m is not None else latest.distance
            latest.tripTime = round(request.duration_minutes) if request.duration_minutes is not None else latest.tripTime
            latest.startPoint = WKTElement(start_point, srid=4326)
            latest.endPoint = WKTElement(end_point, srid=4326)
            latest.isActive = request.is_active
            if current_route is not None and not same_group and current_route.uniqueID != latest.uniqueID:
                current_route.isActive = False
            db.flush()
            _bump_dataset_version(db)
            db.commit()
            db.refresh(latest)
            return _route_payload(db, latest, bus)

    # A changed line becomes a new version; keep all previous rows for history.
    if latest is not None:
        latest.isActive = False

    route = BusRoute(
        busID=bus.uniqueID,
        direction=request.direction,
        lineString=WKTElement(geometry_wkt, srid=4326),
        distance=request.distance_m,
        tripTime=round(request.duration_minutes) if request.duration_minutes is not None else None,
        startPoint=WKTElement(start_point, srid=4326),
        endPoint=WKTElement(end_point, srid=4326),
        isActive=request.is_active,
    )
    db.add(route)
    db.flush()

    if current_route is not None and current_route.uniqueID != route.uniqueID:
        current_route.isActive = False

    _bump_dataset_version(db)
    db.commit()
    db.refresh(route)
    return _route_payload(db, route, bus)


@router.get("")
def get_routes(db: Session = Depends(get_db)):
    rows = (
        db.query(BusRoute, Bus)
        .join(Bus, Bus.uniqueID == BusRoute.busID)
        .filter(BusRoute.isActive.is_(True), Bus.isActive.is_(True))
        .order_by(Bus.uniqueID, BusRoute.direction, BusRoute.version.desc())
        .all()
    )
    latest_by_group = {}
    for route, bus in rows:
        latest_by_group.setdefault((bus.uniqueID, route.direction), (route, bus))
    return [_route_payload(db, route, bus) for route, bus in latest_by_group.values()]


@router.get("/map")
def get_routes_map(db: Session = Depends(get_db)):
    return get_routes(db)


@router.post("/preview")
def preview_route(request: RoutePreviewRequest):
    waypoints = [(point.lon, point.lat) for point in request.waypoints]
    route = calculate_route(waypoints)
    feature = route["features"][0]
    properties = feature.get("properties") or {}
    duration_seconds = float(properties.get("total-time", 0))
    return {
        "route_name": request.name or request.route_name,
        "name": request.name or request.route_name,
        "color": request.color,
        "old_price": request.old_price,
        "new_price": request.new_price if request.new_price is not None else request.fare,
        "direction": request.direction,
        "geometry": feature["geometry"],
        "distance_m": float(properties.get("track-length", 0)),
        "duration_seconds": duration_seconds,
        "duration_minutes": duration_seconds / 60,
    }


@router.post("/brouter-waypoints")
def brouter_waypoints(request: BRouterWaypointsRequest):
    waypoints = [(point.lon, point.lat) for point in request.waypoints]
    route = calculate_route(waypoints)
    feature = route["features"][0]
    properties = feature.get("properties") or {}
    duration_seconds = float(properties.get("total-time", 0))
    return {
        "route_name": request.route_name,
        "geometry": feature["geometry"],
        "distance_m": float(properties.get("track-length", 0)),
        "duration_seconds": duration_seconds,
        "duration_minutes": duration_seconds / 60,
    }


@router.post("")
def save_route(request: RouteSaveRequest, db: Session = Depends(get_db)):
    return _save_route(request, db)


@router.put("/{route_id}")
def update_route(route_id: int, request: RouteSaveRequest, db: Session = Depends(get_db)):
    return _save_route(request, db, existing_route_id=route_id)


@router.delete("/{route_id}")
def delete_route(route_id: int, db: Session = Depends(get_db)):
    route = db.query(BusRoute).filter(BusRoute.uniqueID == route_id).first()
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")

    now = _now()
    db.query(BusRoute).filter(
        BusRoute.busID == route.busID,
        BusRoute.direction == route.direction,
    ).update({"isActive": False}, synchronize_session=False)

    # Keep the BUS record if another direction/version is still active.
    active_other = db.query(BusRoute).filter(
        BusRoute.busID == route.busID,
        BusRoute.isActive.is_(True),
    ).first()
    if active_other is None:
        bus = db.query(Bus).filter(Bus.uniqueID == route.busID).first()
        if bus:
            bus.isActive = False

    _bump_dataset_version(db)
    db.commit()
    return {"id": route_id, "deleted": True}
