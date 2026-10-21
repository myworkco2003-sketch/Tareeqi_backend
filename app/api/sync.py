from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Bus, BusRoute

router = APIRouter(prefix="/api/sync", tags=["App Sync"])

# Version of the SQLite schema consumed by the mobile app.
SCHEMA_VERSION = 2


def read_dataset_version(db: Session) -> int:
    version = db.execute(
        text("SELECT version FROM dataset_version WHERE id = 1")
    ).scalar()
    if version is None:
        raise HTTPException(status_code=500, detail="جدول dataset_version غير مهيأ")
    return int(version)


def load_published_routes(db: Session) -> list[dict]:
    rows = (
        db.query(BusRoute, Bus)
        .join(Bus, Bus.uniqueID == BusRoute.busID)
        .filter(BusRoute.isActive.is_(True), Bus.isActive.is_(True))
        .order_by(Bus.uniqueID, BusRoute.direction, BusRoute.version.desc())
        .all()
    )

    # Only the latest active version per bus + direction is published.
    latest_by_group = {}
    for route, bus in rows:
        latest_by_group.setdefault((bus.uniqueID, route.direction), (route, bus))

    route_ids = [route.uniqueID for route, _ in latest_by_group.values()]
    if not route_ids:
        return []

    geometry_rows = db.execute(
        text(
            """
            SELECT "uniqueID" AS id,
                   ST_AsGeoJSON("lineString", 6)::json AS geometry,
                   COALESCE(distance, ST_Length("lineString"::geography)) AS length_m
            FROM public.bus_route
            WHERE "uniqueID" IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": route_ids},
    ).all()
    geometries = {row.id: row for row in geometry_rows}

    result = []
    for (route, bus) in latest_by_group.values():
        row = geometries.get(route.uniqueID)
        if row is None or not row.geometry:
            continue

        coordinates = row.geometry["coordinates"]
        if len(coordinates) < 2:
            continue

        lons = [point[0] for point in coordinates]
        lats = [point[1] for point in coordinates]
        result.append({
            "id": bus.uniqueID,
            "route_id": route.uniqueID,
            "name": bus.name,
            "color": bus.color,
            "fare": float(bus.newPrice) if bus.newPrice is not None else None,
            "old_price": float(bus.oldPrice) if bus.oldPrice is not None else None,
            "new_price": float(bus.newPrice) if bus.newPrice is not None else None,
            "direction": route.direction,
            "version": route.version,
            "length_m": round(float(row.length_m or 0), 1),
            "trip_time": route.tripTime,
            "min_lon": min(lons),
            "min_lat": min(lats),
            "max_lon": max(lons),
            "max_lat": max(lats),
            "geometry": coordinates,
        })
    return result


@router.get("/manifest")
def get_manifest(db: Session = Depends(get_db)):
    return {
        "data_version": read_dataset_version(db),
        "schema_version": SCHEMA_VERSION,
    }


@router.get("/routes")
def get_routes(db: Session = Depends(get_db)):
    # Avoid returning a mixed snapshot if the dataset changes during the read.
    for _ in range(3):
        before = read_dataset_version(db)
        routes = load_published_routes(db)
        after = read_dataset_version(db)
        if before == after:
            return {
                "data_version": after,
                "schema_version": SCHEMA_VERSION,
                "routes": routes,
            }

    raise HTTPException(
        status_code=503,
        detail="البيانات قيد التحديث، أعد المحاولة بعد لحظات",
    )
