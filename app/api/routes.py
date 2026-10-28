
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas import (
    BRouterWaypointsRequest,
    BusRouteAddDirectionRequest,
    BusWithRouteCreateRequest,
    BusWithRouteUpdateRequest,
    RoutePreviewRequest,
)
from app.db.database import get_db
from app.db.models import Bus, BusRoute
from app.services.brouter_service import calculate_route


router = APIRouter(
    prefix="/admin/routes",
    tags=["Admin Routes"],
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_wkt(geometry: dict) -> str:
    if geometry.get("type") != "LineString":
        raise HTTPException(
            status_code=422,
            detail="Geometry must be a LineString",
        )

    coordinates = geometry.get("coordinates")

    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise HTTPException(
            status_code=422,
            detail="LineString must contain at least two coordinates",
        )

    points = []

    for point in coordinates:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise HTTPException(
                status_code=422,
                detail="Invalid coordinate in LineString",
            )

        lon, lat = point[0], point[1]

        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise HTTPException(
                status_code=422,
                detail="Coordinate is outside valid longitude/latitude bounds",
            )

        points.append(f"{lon} {lat}")

    return "LINESTRING(" + ", ".join(points) + ")"


def _calculate_from_waypoints(waypoints):
    points = [(point.lon, point.lat) for point in waypoints]

    try:
        result = calculate_route(points)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Failed to calculate route",
        ) from exc

    features = result.get("features") or []

    if not features:
        raise HTTPException(
            status_code=502,
            detail="Routing service returned no route",
        )

    feature = features[0]
    geometry = feature.get("geometry")
    properties = feature.get("properties") or {}

    if not geometry:
        raise HTTPException(
            status_code=502,
            detail="Routing service returned no geometry",
        )

    distance_m = float(properties.get("track-length", 0))
    trip_time_s = int(properties.get("total-time", 0))

    if distance_m < 0 or trip_time_s < 0:
        raise HTTPException(
            status_code=502,
            detail="Routing service returned invalid distance or duration",
        )

    # Validate the returned geometry before saving it.
    _to_wkt(geometry)

    return geometry, distance_m, trip_time_s


def _route_geometry(db: Session, route: BusRoute):
    return db.execute(
        text(
            """
            SELECT ST_AsGeoJSON(line_string)::json
            FROM bus_route
            WHERE id = :route_id
            """
        ),
        {"route_id": route.id},
    ).scalar()


def _route_response(db: Session, route: BusRoute):
    return {
        "id": route.id,
        "bus_id": route.bus_id,
        "route_name": route.bus.name,
        "name": route.bus.name,
        "color": route.bus.color,
        "old_price": (
            float(route.bus.old_price)
            if route.bus.old_price is not None
            else None
        ),
        "new_price": (
            float(route.bus.new_price)
            if route.bus.new_price is not None
            else None
        ),
        "fare": (
            float(route.bus.new_price)
            if route.bus.new_price is not None
            else None
        ),
        "direction": route.direction,
        "version": route.version,
        "start_point": route.start_point,
        "end_point": route.end_point,
        "distance_m": route.distance_m,
        "trip_time_s": route.trip_time_s,
        "is_active": route.is_active,
        "geometry": _route_geometry(db, route),
    }


def _next_version(db: Session, bus_id: int, direction: str) -> int:
    current_version = (
        db.query(func.max(BusRoute.version))
        .filter(
            BusRoute.bus_id == bus_id,
            BusRoute.direction == direction,
        )
        .scalar()
    )

    return (current_version or 0) + 1


def _deactivate_active_direction(
    db: Session,
    bus_id: int,
    direction: str,
    now: datetime,
):
    db.query(BusRoute).filter(
        BusRoute.bus_id == bus_id,
        BusRoute.direction == direction,
        BusRoute.is_active.is_(True),
    ).update(
        {
            BusRoute.is_active: False,
            BusRoute.updated_at: now,
        },
        synchronize_session=False,
    )


def _bump_dataset_version(db: Session):
    # Keep this only if the existing dataset_version table is still used.
    db.execute(
        text(
            """
            UPDATE dataset_version
            SET version = version + 1,
                updated_at = now()
            WHERE id = 1
            """
        )
    )


def _finish_change(db: Session):
    _bump_dataset_version(db)
    db.commit()


@router.get("")
def get_routes(db: Session = Depends(get_db)):
    routes = (
        db.query(BusRoute)
        .join(Bus, Bus.id == BusRoute.bus_id)
        .filter(
            Bus.is_active.is_(True),
            BusRoute.is_active.is_(True),
        )
        .order_by(Bus.name, BusRoute.direction)
        .all()
    )

    return [
        {
            "id": route.id,
            "bus_id": route.bus_id,
            "route_name": route.bus.name,
            "name": route.bus.name,
            "color": route.bus.color,
            "direction": route.direction,
            "version": route.version,
            "is_active": route.is_active,
            "start_point": route.start_point,
            "end_point": route.end_point,
            "distance_m": route.distance_m,
            "trip_time_s": route.trip_time_s,
            "fare": (
                float(route.bus.new_price)
                if route.bus.new_price is not None
                else None
            ),
        }
        for route in routes
    ]


@router.get("/map")
def get_routes_map(db: Session = Depends(get_db)):
    routes = (
        db.query(BusRoute)
        .join(Bus, Bus.id == BusRoute.bus_id)
        .filter(
            Bus.is_active.is_(True),
            BusRoute.is_active.is_(True),
        )
        .order_by(Bus.name, BusRoute.direction)
        .all()
    )

    return [
        {
            "id": route.id,
            "bus_id": route.bus_id,
            "route_name": route.bus.name,
            "color": route.bus.color,
            "fare": (
                float(route.bus.new_price)
                if route.bus.new_price is not None
                else None
            ),
            "direction": route.direction,
            "version": route.version,
            "start_point": route.start_point,
            "end_point": route.end_point,
            "distance_m": route.distance_m,
            "trip_time_s": route.trip_time_s,
            "geometry": _route_geometry(db, route),
        }
        for route in routes
    ]


@router.post("/preview")
def preview_route(request: RoutePreviewRequest):
    geometry, distance_m, trip_time_s = _calculate_from_waypoints(
        request.waypoints
    )

    return {
        "geometry": geometry,
        "distance_m": distance_m,
        "trip_time_s": trip_time_s,
        "duration_seconds": trip_time_s,
        "duration_minutes": trip_time_s / 60,
    }


@router.post("/brouter-waypoints")
def brouter_waypoints(request: BRouterWaypointsRequest):
    geometry, distance_m, trip_time_s = _calculate_from_waypoints(
        request.waypoints
    )

    return {
        "geometry": geometry,
        "distance_m": distance_m,
        "trip_time_s": trip_time_s,
        "duration_seconds": trip_time_s,
        "duration_minutes": trip_time_s / 60,
    }


@router.post("")
def create_bus_with_route(
    request: BusWithRouteCreateRequest,
    db: Session = Depends(get_db),
):
    now = _now()

    try:
        existing_bus = (
            db.query(Bus)
            .filter(Bus.name == request.name)
            .first()
        )

        if existing_bus:
            raise HTTPException(
                status_code=409,
                detail="A bus with this name already exists",
            )

        geometry, distance_m, trip_time_s = _calculate_from_waypoints(
            request.waypoints
        )

        bus = Bus(
            name=request.name,
            color=request.color,
            old_price=None,
            new_price=request.price,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        db.add(bus)
        db.flush()

        route = BusRoute(
            bus_id=bus.id,
            version=1,
            line_string=WKTElement(_to_wkt(geometry), srid=4326),
            distance_m=distance_m,
            trip_time_s=trip_time_s,
            direction=request.direction,
            start_point=request.start_point,
            end_point=request.end_point,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        db.add(route)
        db.flush()

        _finish_change(db)

        return {
            "id": route.id,
            "bus_id": bus.id,
            "route_name": bus.name,
            "version": route.version,
            "direction": route.direction,
            "old_price": None,
            "new_price": float(bus.new_price),
        }

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Could not create bus and route because of a database constraint",
        ) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/buses/{bus_id}/routes")
def add_direction_to_existing_bus(
    bus_id: int,
    request: BusRouteAddDirectionRequest,
    db: Session = Depends(get_db),
):
    bus = (
        db.query(Bus)
        .filter(Bus.id == bus_id)
        .with_for_update()
        .first()
    )

    if not bus or not bus.is_active:
        raise HTTPException(
            status_code=404,
            detail="Bus not found or inactive",
        )

    existing_direction = (
        db.query(BusRoute)
        .filter(
            BusRoute.bus_id == bus_id,
            BusRoute.direction == request.direction,
            BusRoute.is_active.is_(True),
        )
        .first()
    )

    if existing_direction:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Bus already has an active route "
                f"for direction: {request.direction}"
            ),
        )

    geometry, distance_m, trip_time_s = (
        _calculate_from_waypoints(request.waypoints)
    )

    now = _now()
    next_version = _next_version(db, bus_id, request.direction)

    new_route = BusRoute(
        bus_id=bus.id,
        version=next_version,
        line_string=WKTElement(_to_wkt(geometry), srid=4326),
        distance_m=distance_m,
        trip_time_s=trip_time_s,
        direction=request.direction,
        start_point=request.start_point,
        end_point=request.end_point,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    db.add(new_route)

    try:
        db.flush()
        _finish_change(db)
    except Exception:
        db.rollback()
        raise

    return {
        "id": new_route.id,
        "bus_id": bus.id,
        "route_name": bus.name,
        "name": bus.name,
        "color": bus.color,
        "version": new_route.version,
        "direction": new_route.direction,
        "start_point": new_route.start_point,
        "end_point": new_route.end_point,
        "distance_m": new_route.distance_m,
        "trip_time_s": new_route.trip_time_s,
        "is_active": new_route.is_active,
        "fare": bus.new_price,
    }


@router.put("/{route_id}")
def update_bus_with_route(
    route_id: int,
    request: BusWithRouteUpdateRequest,
    db: Session = Depends(get_db),
):
    now = _now()

    try:
        route = (
            db.query(BusRoute)
            .filter(BusRoute.id == route_id)
            .with_for_update()
            .first()
        )

        if not route:
            raise HTTPException(
                status_code=404,
                detail="Route not found",
            )

        bus = (
            db.query(Bus)
            .filter(Bus.id == route.bus_id)
            .with_for_update()
            .first()
        )

        if not bus or not bus.is_active:
            raise HTTPException(
                status_code=404,
                detail="Active bus not found",
            )

        if not route.is_active:
            raise HTTPException(
                status_code=409,
                detail="Only the active route version can be edited",
            )

        if request.direction != route.direction:
            raise HTTPException(
                status_code=409,
                detail="The route direction cannot be changed during editing",
            )

        if request.name is not None and request.name != bus.name:
            duplicate = (
                db.query(Bus)
                .filter(
                    Bus.name == request.name,
                    Bus.id != bus.id,
                )
                .first()
            )

            if duplicate:
                raise HTTPException(
                    status_code=409,
                    detail="A bus with this name already exists",
                )

            bus.name = request.name

        if request.color is not None:
            bus.color = request.color

        if request.price is not None:
            current_price = (
                float(bus.new_price)
                if bus.new_price is not None
                else None
            )

            if current_price != request.price:
                bus.old_price = bus.new_price
                bus.new_price = request.price

        bus.updated_at = now

        geometry, distance_m, trip_time_s = _calculate_from_waypoints(
            request.waypoints
        )

        # Create a new version for this direction only.
        next_version = _next_version(
            db,
            bus.id,
            route.direction,
        )

        _deactivate_active_direction(
            db,
            bus.id,
            route.direction,
            now,
        )

        new_route = BusRoute(
            bus_id=bus.id,
            version=next_version,
            line_string=WKTElement(_to_wkt(geometry), srid=4326),
            distance_m=distance_m,
            trip_time_s=trip_time_s,
            direction=route.direction,
            start_point=request.start_point,
            end_point=request.end_point,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        db.add(new_route)
        db.flush()

        _finish_change(db)

        return {
            "id": new_route.id,
            "bus_id": bus.id,
            "route_name": bus.name,
            "version": new_route.version,
            "direction": new_route.direction,
            "old_price": (
                float(bus.old_price)
                if bus.old_price is not None
                else None
            ),
            "new_price": (
                float(bus.new_price)
                if bus.new_price is not None
                else None
            ),
        }

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Could not update bus and route because of a database constraint",
        ) from exc
    except Exception:
        db.rollback()
        raise


@router.delete("/{route_id}")
def deactivate_route(
    route_id: int,
    db: Session = Depends(get_db),
):
    now = _now()

    try:
        route = (
            db.query(BusRoute)
            .filter(BusRoute.id == route_id)
            .with_for_update()
            .first()
        )

        if not route:
            raise HTTPException(
                status_code=404,
                detail="Route not found",
            )

        if route.is_active:
            route.is_active = False
            route.updated_at = now

            _finish_change(db)
        else:
            db.rollback()

        return {
            "id": route.id,
            "bus_id": route.bus_id,
            "deleted": True,
            "is_active": False,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.delete("/buses/{bus_id}")
def deactivate_bus(
    bus_id: int,
    db: Session = Depends(get_db),
):
    now = _now()

    try:
        bus = (
            db.query(Bus)
            .filter(Bus.id == bus_id)
            .with_for_update()
            .first()
        )

        if not bus:
            raise HTTPException(
                status_code=404,
                detail="Bus not found",
            )

        bus.is_active = False
        bus.updated_at = now

        db.query(BusRoute).filter(
            BusRoute.bus_id == bus.id,
            BusRoute.is_active.is_(True),
        ).update(
            {
                BusRoute.is_active: False,
                BusRoute.updated_at: now,
            },
            synchronize_session=False,
        )

        _finish_change(db)

        return {
            "id": bus.id,
            "deleted": True,
            "is_active": False,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
