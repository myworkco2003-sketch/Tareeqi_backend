from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.api.schemas import (
    RoutePreviewRequest,
    RouteSaveRequest,
    BRouterWaypointsRequest,
)
from app.db.database import get_db
from app.db.models import MinibusRoute, RouteVersion, RouteFare
from app.services.brouter_service import calculate_route
from geoalchemy2.elements import WKTElement
from sqlalchemy import text
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(
    prefix="/admin/routes",
    tags=["Admin Routes"],
)

def _bump_dataset_version(db: Session):
    db.execute(
        text(
            "UPDATE dataset_version "
            "SET version = version + 1, updated_at = now() "
            "WHERE id = 1"
        )
    )

def _to_wkt(geometry: dict) -> str:
    return "LINESTRING(" + ", ".join(
        f"{point[0]} {point[1]}" for point in geometry["coordinates"]
    ) + ")"


@router.get("")
def get_routes(
    db: Session = Depends(get_db),
):
    routes = (
        db.query(MinibusRoute)
        .order_by(MinibusRoute.id)
        .all()
    )

    return [
        {
            "id": route.id,
            "route_name": route.route_name,
            "color": route.color,
            "is_active": route.is_active,
        }
        for route in routes
    ]



@router.get("/map")
def get_routes_map(
    db: Session = Depends(get_db),
):
    routes = (
        db.query(MinibusRoute)
        .order_by(MinibusRoute.id)
        .all()
    )

    result = []

    for route in routes:
        active_version = (
            db.query(RouteVersion)
            .filter(
                RouteVersion.route_id == route.id,
                RouteVersion.is_active.is_(True),
            )
            .order_by(RouteVersion.version.desc())
            .first()
        )

        if not active_version:
            continue

        geometry = db.execute(
            text(
                """
                SELECT ST_AsGeoJSON(geom)::json
                FROM route_versions
                WHERE id = :version_id
                """
            ),
            {"version_id": active_version.id},
        ).scalar()

        fare = (
            db.query(RouteFare)
            .filter(
                RouteFare.route_id == route.id,
                RouteFare.is_valid.is_(True),
            )
            .order_by(RouteFare.updated_at.desc())
            .first()
        )

        result.append(
            {
                "id": route.id,
                "route_name": route.route_name,
                "color": route.color,
                "fare": float(fare.fare) if fare else None,
                "geometry": geometry,
            }
        )

    return result


@router.post("/preview")
def preview_route(request: RoutePreviewRequest):
    waypoints = [
        (point.lon, point.lat)
        for point in request.waypoints
    ]

    route = calculate_route(waypoints)

    feature = route["features"][0]
    properties = feature["properties"]

    return {
        "route_name": request.route_name,
        "color": request.color,
        "fare": request.fare,
        "geometry": feature["geometry"],
        "distance_m": float(properties.get("track-length", 0)),
        "duration_seconds": int(properties.get("total-time", 0)),
        "duration_minutes": (
            int(properties.get("total-time", 0)) / 60
        ),
    }



@router.post("/brouter-waypoints")
def brouter_waypoints(request: BRouterWaypointsRequest):
    waypoints = [
        (point.lon, point.lat)
        for point in request.waypoints
    ]

    route = calculate_route(waypoints)

    feature = route["features"][0]
    properties = feature["properties"]

    return {
        "route_name": request.route_name,
        "geometry": feature["geometry"],
        "distance_m": float(properties.get("track-length", 0)),
        "duration_seconds": int(properties.get("total-time", 0)),
        "duration_minutes": (
            int(properties.get("total-time", 0)) / 60
        ),
    }


@router.post("")
def save_route(
    request: RouteSaveRequest,
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    route = MinibusRoute(
        route_name=request.route_name,
        color=request.color,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    db.add(route)
    db.flush()

    version = RouteVersion(
        route_id=route.id,
        version=1,
        geom=WKTElement(_to_wkt(request.geometry), srid=4326),
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    fare = RouteFare(
        route_id=route.id,
        fare=request.fare,
        is_valid=True,
        created_at=now,
        updated_at=now,
    )

    db.add(version)
    db.add(fare)

    db.flush()

    db.execute(text("SELECT rebuild_super_graph()"))
    _bump_dataset_version(db)
    db.commit()

    return {
        "id": route.id,
        "route_name": route.route_name,
        "version": version.version,
        "fare": float(fare.fare),
    }



@router.put("/{route_id}")
def update_route(
    route_id: int,
    request: RouteSaveRequest,
    db: Session = Depends(get_db),
):
    route = db.query(MinibusRoute).filter(MinibusRoute.id == route_id).first()

    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    now = datetime.now(timezone.utc)

    route.route_name = request.route_name
    route.color = request.color
    route.updated_at = now

    last_version = (
        db.query(RouteVersion)
        .filter(RouteVersion.route_id == route_id)
        .order_by(RouteVersion.version.desc())
        .first()
    )
    next_version = (last_version.version + 1) if last_version else 1

    # نطفّي النسخ القديمة
    db.query(RouteVersion).filter(
        RouteVersion.route_id == route_id,
        RouteVersion.is_active.is_(True),
    ).update({"is_active": False, "updated_at": now})

    version = RouteVersion(
        route_id=route_id,
        version=next_version,
        geom=WKTElement(_to_wkt(request.geometry), srid=4326),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(version)

    # الأجرة: نعمل أجرة جديدة بس إذا تغيّرت
    valid_fares = (
        db.query(RouteFare)
        .filter(
            RouteFare.route_id == route_id,
            RouteFare.is_valid.is_(True),
        )
        .all()
    )

    if not any(float(f.fare) == request.fare for f in valid_fares):
        for old_fare in valid_fares:
            old_fare.is_valid = False
            old_fare.updated_at = now

        db.add(
            RouteFare(
                route_id=route_id,
                fare=request.fare,
                is_valid=True,
                created_at=now,
                updated_at=now,
            )
        )

    db.flush()

    db.execute(text("SELECT rebuild_super_graph()"))
    _bump_dataset_version(db)
    db.commit()

    return {
        "id": route.id,
        "route_name": route.route_name,
        "version": version.version,
        "fare": request.fare,
    }


@router.delete("/{route_id}")
def delete_route(
    route_id: int,
    db: Session = Depends(get_db),
):
    route = db.query(MinibusRoute).filter(MinibusRoute.id == route_id).first()

    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    now = datetime.now(timezone.utc)

    route.is_active = False
    route.updated_at = now

    db.query(RouteVersion).filter(
        RouteVersion.route_id == route_id
    ).update({"is_active": False, "updated_at": now})

    db.query(RouteFare).filter(
        RouteFare.route_id == route_id
    ).update({"is_valid": False, "updated_at": now})

    db.flush()

    db.execute(text("SELECT rebuild_super_graph()"))
    _bump_dataset_version(db)
    db.commit()

    return {"id": route_id, "deleted": True}