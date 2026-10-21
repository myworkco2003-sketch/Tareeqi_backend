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


def _geometry_json(db: Session, route_id: int):
    return db.execute(
        text(
            'SELECT ST_AsGeoJSON("lineString")::json '
            'FROM public.bus_route WHERE "uniqueID" = :route_id'
        ),
        {"route_id": route_id},
    ).scalar()


def _bus_payload(bus: Bus) -> dict:
    return {
        "uniqueID": bus.uniqueID,
        "name": bus.name,
        "color": bus.color,
        "oldPrice": float(bus.oldPrice) if bus.oldPrice is not None else None,
        "newPrice": float(bus.newPrice) if bus.newPrice is not None else None,
        "isActive": bus.isActive,
    }


def _route_payload(db: Session, route: BusRoute, bus: Bus) -> dict:
    return {
        "uniqueID": route.uniqueID,
        "busID": route.busID,
        "bus": _bus_payload(bus),
        "version": route.version,
        "lineString": _geometry_json(db, route.uniqueID),
        "distance": float(route.distance) if route.distance is not None else None,
        "tripTime": route.tripTime,
        "direction": route.direction,
        "startPoint": db.execute(
            text(
                'SELECT ST_AsGeoJSON("startPoint")::json '
                'FROM public.bus_route WHERE "uniqueID" = :route_id'
            ),
            {"route_id": route.uniqueID},
        ).scalar(),
        "endPoint": db.execute(
            text(
                'SELECT ST_AsGeoJSON("endPoint")::json '
                'FROM public.bus_route WHERE "uniqueID" = :route_id'
            ),
            {"route_id": route.uniqueID},
        ).scalar(),
        "isActive": route.isActive,
    }


# BUS endpoints ---------------------------------------------------------------

@router.get("/buses")
def list_buses(db: Session = Depends(get_db)):
    buses = db.query(Bus).order_by(Bus.uniqueID).all()
    return [_bus_payload(bus) for bus in buses]


@router.post("/buses", status_code=201)
def create_bus(request: BusCreateRequest, db: Session = Depends(get_db)):
    bus = Bus(
        name=request.name.strip(),
        color=request.color,
        oldPrice=request.old_price,
        newPrice=request.new_price,
        isActive=request.is_active,
    )
    db.add(bus)
    db.commit()
    db.refresh(bus)
    return _bus_payload(bus)


@router.get("/buses/{bus_id}")
def get_bus(bus_id: int, db: Session = Depends(get_db)):
    bus = db.query(Bus).filter(Bus.uniqueID == bus_id).first()
    if bus is None:
        raise HTTPException(status_code=404, detail="Bus not found")
    return _bus_payload(bus)


@router.patch("/buses/{bus_id}")
def update_bus(bus_id: int, request: BusUpdateRequest, db: Session = Depends(get_db)):
    bus = (
        db.query(Bus)
        .filter(Bus.uniqueID == bus_id)
        .with_for_update()
        .first()
    )
    if bus is None:
        raise HTTPException(status_code=404, detail="Bus not found")

    values = request.model_dump(exclude_unset=True)
    field_map = {
        "name": "name",
        "color": "color",
        "old_price": "oldPrice",
        "new_price": "newPrice",
        "is_active": "isActive",
    }
    for key, value in values.items():
        setattr(bus, field_map[key], value.strip() if key == "name" and value else value)

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
    query = db.query(BusRoute, Bus).join(Bus, Bus.uniqueID == BusRoute.busID)
    if bus_id is not None:
        query = query.filter(BusRoute.busID == bus_id)
    if direction is not None:
        query = query.filter(BusRoute.direction == direction)
    if not include_inactive:
        query = query.filter(BusRoute.isActive.is_(True), Bus.isActive.is_(True))

    rows = query.order_by(
        BusRoute.busID, BusRoute.direction, BusRoute.version.desc()
    ).all()
    return [_route_payload(db, route, bus) for route, bus in rows]


@router.get("/routes/map")
def list_active_routes_for_map(db: Session = Depends(get_db)):
    rows = (
        db.query(BusRoute, Bus)
        .join(Bus, Bus.uniqueID == BusRoute.busID)
        .filter(BusRoute.isActive.is_(True), Bus.isActive.is_(True))
        .order_by(BusRoute.busID, BusRoute.direction)
        .all()
    )
    return [_route_payload(db, route, bus) for route, bus in rows]


@router.post("/routes/preview")
def preview_route(request: RoutePreviewRequest):
    waypoints = [(point.lon, point.lat) for point in request.waypoints]
    response = calculate_route(waypoints)
    feature = response["features"][0]
    properties = feature.get("properties") or {}
    duration_seconds = float(properties.get("total-time", 0))
    return {
        "geometry": feature["geometry"],
        "distance": float(properties.get("track-length", 0)),
        "tripTime": duration_seconds / 60,
        "duration_seconds": duration_seconds,
    }


@router.post("/routes/brouter-waypoints")
def brouter_waypoints(request: BRouterWaypointsRequest):
    waypoints = [(point.lon, point.lat) for point in request.waypoints]
    response = calculate_route(waypoints)
    feature = response["features"][0]
    properties = feature.get("properties") or {}
    duration_seconds = float(properties.get("total-time", 0))
    return {
        "geometry": feature["geometry"],
        "distance": float(properties.get("track-length", 0)),
        "tripTime": duration_seconds / 60,
    }


def _save_route(request: RouteSaveRequest, db: Session, route_id: int | None = None):
    bus = (
        db.query(Bus)
        .filter(Bus.uniqueID == request.bus_id)
        .with_for_update()
        .first()
    )
    if bus is None:
        raise HTTPException(status_code=404, detail="Bus not found")

    lock_key = f"bus-route:{request.bus_id}:{request.direction}"
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": lock_key},
    )

    current = None
    if route_id is not None:
        current = (
            db.query(BusRoute)
            .filter(BusRoute.uniqueID == route_id)
            .with_for_update()
            .first()
        )
        if current is None:
            raise HTTPException(status_code=404, detail="Bus route not found")
        if current.busID != request.bus_id:
            raise HTTPException(status_code=422, detail="bus_id cannot be changed for an existing route")

    latest = (
        db.query(BusRoute)
        .filter(
            BusRoute.busID == request.bus_id,
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
                'SELECT ST_AsEWKB("lineString") = '
                'ST_AsEWKB(ST_GeomFromText(:line_wkt, 4326)) '
                'FROM public.bus_route WHERE "uniqueID" = :route_id'
            ),
            {"line_wkt": line_wkt, "route_id": latest.uniqueID},
        ).scalar()

        if same_geometry:
            latest.distance = request.distance_m
            latest.tripTime = round(request.duration_minutes)
            latest.startPoint = WKTElement(start_wkt, srid=4326)
            latest.endPoint = WKTElement(end_wkt, srid=4326)
            latest.isActive = request.is_active
            db.commit()
            db.refresh(latest)
            return _route_payload(db, latest, bus)

    # The database trigger assigns version and deactivates the prior version.
    route = BusRoute(
        busID=request.bus_id,
        direction=request.direction,
        lineString=WKTElement(line_wkt, srid=4326),
        distance=request.distance_m,
        tripTime=round(request.duration_minutes),
        startPoint=WKTElement(start_wkt, srid=4326),
        endPoint=WKTElement(end_wkt, srid=4326),
        isActive=request.is_active,
    )
    db.add(route)
    db.flush()

    # If an old row was explicitly edited, preserve it in history but mark inactive.
    if current is not None and current.uniqueID != route.uniqueID:
        current.isActive = False

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
    route = (
        db.query(BusRoute)
        .filter(BusRoute.uniqueID == route_id)
        .with_for_update()
        .first()
    )
    if route is None:
        raise HTTPException(status_code=404, detail="Bus route not found")

    route.isActive = False
    db.commit()
    return {"uniqueID": route.uniqueID, "isActive": False}
