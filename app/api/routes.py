from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.elements import WKTElement
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import (
    BRouterWaypointsRequest,
    BusCreateRequest,
    BusUpdateRequest,
    RoutePreviewRequest,
    RouteSaveRequest,
)
from app.db.database import get_db
from app.db.models import Bus, BusRoute
from app.services.brouter_service import calculate_route

router = APIRouter(prefix="/admin", tags=["Admin"])


def _line_wkt(geometry: dict) -> str:
    coordinates = geometry["coordinates"]
    return "LINESTRING(" + ", ".join(
        f"{float(point[0])} {float(point[1])}" for point in coordinates
    ) + ")"


def _point_wkt(point: dict | None, fallback: list[float]) -> str:
    lon = float(point["lon"]) if point else float(fallback[0])
    lat = float(point["lat"]) if point else float(fallback[1])
    return f"POINT({lon} {lat})"


def _bump_dataset_version(db: Session) -> None:
    # Keep the existing mobile delta-sync contract intact.
    db.execute(
        text(
            "UPDATE dataset_version "
            "SET version = version + 1, updated_at = now() "
            "WHERE id = 1"
        )
    )


def _geometry_json(db: Session, route_id: int, column: str):
    # column is chosen only from this fixed internal allowlist.
    if column not in {"line_string", "start_point", "end_point"}:
        raise ValueError("Unsupported geometry column")
    return db.execute(
        text(
            f'SELECT ST_AsGeoJSON("{column}")::json '
            'FROM public.bus_route WHERE id = :route_id'
        ),
        {"route_id": route_id},
    ).scalar()


def _bus_payload(bus: Bus) -> dict:
    return {
        "id": bus.id,
        "name": bus.name,
        "color": bus.color,
        "old_price": float(bus.old_price) if bus.old_price is not None else None,
        "new_price": float(bus.new_price) if bus.new_price is not None else None,
        "is_active": bus.is_active,
    }


def _route_payload(db: Session, route: BusRoute, bus: Bus) -> dict:
    return {
        "id": route.id,
        "bus_id": route.bus_id,
        "bus": _bus_payload(bus),
        "version": route.version,
        "line_string": _geometry_json(db, route.id, "line_string"),
        "distance": float(route.distance) if route.distance is not None else None,
        "trip_time": route.trip_time,
        "direction": route.direction,
        "start_point": _geometry_json(db, route.id, "start_point"),
        "end_point": _geometry_json(db, route.id, "end_point"),
        "is_active": route.is_active,
    }


# BUS endpoints ---------------------------------------------------------------

@router.get("/buses")
def list_buses(db: Session = Depends(get_db)):
    return [
        _bus_payload(bus)
        for bus in db.query(Bus).order_by(Bus.id).all()
    ]


@router.post("/buses", status_code=201)
def create_bus(request: BusCreateRequest, db: Session = Depends(get_db)):
    bus = Bus(
        name=request.name.strip(),
        color=request.color,
        old_price=request.old_price,
        new_price=request.new_price,
        is_active=request.is_active,
    )
    db.add(bus)
    db.flush()
    _bump_dataset_version(db)
    db.commit()
    db.refresh(bus)
    return _bus_payload(bus)


@router.get("/buses/{bus_id}")
def get_bus(bus_id: int, db: Session = Depends(get_db)):
    bus = db.query(Bus).filter(Bus.id == bus_id).first()
    if bus is None:
        raise HTTPException(status_code=404, detail="Bus not found")
    return _bus_payload(bus)


@router.patch("/buses/{bus_id}")
def update_bus(bus_id: int, request: BusUpdateRequest, db: Session = Depends(get_db)):
    bus = db.query(Bus).filter(Bus.id == bus_id).with_for_update().first()
    if bus is None:
        raise HTTPException(status_code=404, detail="Bus not found")

    for key, value in request.model_dump(exclude_unset=True).items():
        if key == "name" and value is not None:
            value = value.strip()
            if not value:
                raise HTTPException(status_code=422, detail="Bus name cannot be empty")
        setattr(bus, key, value)

    _bump_dataset_version(db)
    db.commit()
    db.refresh(bus)
    return _bus_payload(bus)


# BUS_ROUTE endpoints ---------------------------------------------------------

@router.get("/routes")
def list_routes(
    bus_id: int | None = None,
    direction: str | None = None,
    include_inactive: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(BusRoute, Bus).join(Bus, Bus.id == BusRoute.bus_id)
    if bus_id is not None:
        query = query.filter(BusRoute.bus_id == bus_id)
    if direction is not None:
        query = query.filter(BusRoute.direction == direction)
    if not include_inactive:
        query = query.filter(BusRoute.is_active.is_(True), Bus.is_active.is_(True))

    rows = query.order_by(
        BusRoute.bus_id, BusRoute.direction, BusRoute.version.desc()
    ).all()
    return [_route_payload(db, route, bus) for route, bus in rows]


@router.get("/routes/map")
def list_active_routes_for_map(db: Session = Depends(get_db)):
    rows = (
        db.query(BusRoute, Bus)
        .join(Bus, Bus.id == BusRoute.bus_id)
        .filter(BusRoute.is_active.is_(True), Bus.is_active.is_(True))
        .order_by(BusRoute.bus_id, BusRoute.direction)
        .all()
    )
    return [_route_payload(db, route, bus) for route, bus in rows]


def _brouter_result(waypoints: list[tuple[float, float]]) -> dict:
    response = calculate_route(waypoints)
    features = response.get("features") or []
    if not features:
        raise HTTPException(status_code=502, detail="BRouter returned no route")
    feature = features[0]
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates")
    if geometry.get("type") != "LineString" or not isinstance(coordinates, list) or len(coordinates) < 2:
        raise HTTPException(status_code=502, detail="BRouter returned invalid LineString")

    properties = feature.get("properties") or {}
    distance = float(properties.get("track-length", 0))
    duration_seconds = float(properties.get("total-time", 0))
    return {
        "geometry": geometry,
        "distance": distance,
        "trip_time": round(duration_seconds / 60),
        "duration_seconds": duration_seconds,
        "duration_minutes": duration_seconds / 60,
    }


@router.post("/routes/preview")
def preview_route(request: RoutePreviewRequest):
    return _brouter_result([(point.lon, point.lat) for point in request.waypoints])


@router.post("/routes/brouter-waypoints")
def brouter_waypoints(request: BRouterWaypointsRequest):
    result = _brouter_result([(point.lon, point.lat) for point in request.waypoints])
    return {
        "route_name": request.route_name,
        **result,
    }


def _save_route(request: RouteSaveRequest, db: Session, route_id: int | None = None):
    bus = db.query(Bus).filter(Bus.id == request.bus_id).with_for_update().first()
    if bus is None:
        raise HTTPException(status_code=404, detail="Bus not found")

    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": f"bus-route:{request.bus_id}:{request.direction}"},
    )

    current = None
    if route_id is not None:
        current = (
            db.query(BusRoute)
            .filter(BusRoute.id == route_id)
            .with_for_update()
            .first()
        )
        if current is None:
            raise HTTPException(status_code=404, detail="Bus route not found")
        if current.bus_id != request.bus_id:
            raise HTTPException(status_code=422, detail="bus_id cannot change for an existing route")

    latest = (
        db.query(BusRoute)
        .filter(
            BusRoute.bus_id == request.bus_id,
            BusRoute.direction == request.direction,
        )
        .order_by(BusRoute.version.desc())
        .with_for_update()
        .first()
    )

    coordinates = request.geometry["coordinates"]
    line_wkt = _line_wkt(request.geometry)
    start_wkt = _point_wkt(
        request.start_point.model_dump() if request.start_point else None,
        coordinates[0],
    )
    end_wkt = _point_wkt(
        request.end_point.model_dump() if request.end_point else None,
        coordinates[-1],
    )

    if latest is not None:
        same_geometry = db.execute(
            text(
                'SELECT ST_AsEWKB("line_string") = '
                'ST_AsEWKB(ST_GeomFromText(:line_wkt, 4326)) '
                'FROM public.bus_route WHERE id = :route_id'
            ),
            {"line_wkt": line_wkt, "route_id": latest.id},
        ).scalar()

        if same_geometry:
            latest.distance = request.distance
            latest.trip_time = round(request.trip_time)
            latest.start_point = WKTElement(start_wkt, srid=4326)
            latest.end_point = WKTElement(end_wkt, srid=4326)
            latest.is_active = request.is_active
            _bump_dataset_version(db)
            db.commit()
            db.refresh(latest)
            return _route_payload(db, latest, bus)

    # Database trigger sets version from bus_id + direction + line_string.
    route = BusRoute(
        bus_id=request.bus_id,
        direction=request.direction,
        line_string=WKTElement(line_wkt, srid=4326),
        distance=request.distance,
        trip_time=round(request.trip_time),
        start_point=WKTElement(start_wkt, srid=4326),
        end_point=WKTElement(end_wkt, srid=4326),
        is_active=request.is_active,
    )
    db.add(route)
    db.flush()

    _bump_dataset_version(db)
    db.commit()
    db.refresh(route)
    return _route_payload(db, route, bus)


@router.post("/routes", status_code=201)
def create_route(request: RouteSaveRequest, db: Session = Depends(get_db)):
    return _save_route(request, db)


@router.put("/routes/{route_id}")
def update_route(route_id: int, request: RouteSaveRequest, db: Session = Depends(get_db)):
    return _save_route(request, db, route_id=route_id)


@router.delete("/routes/{route_id}")
def deactivate_route(route_id: int, db: Session = Depends(get_db)):
    route = db.query(BusRoute).filter(BusRoute.id == route_id).with_for_update().first()
    if route is None:
        raise HTTPException(status_code=404, detail="Bus route not found")
    route.is_active = False
    _bump_dataset_version(db)
    db.commit()
    return {"id": route.id, "is_active": False}
