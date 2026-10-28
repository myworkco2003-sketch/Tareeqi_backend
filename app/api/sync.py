
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session, joinedload

from app.db.database import get_db
from app.db.models import Bus, BusRoute


# مسارات عامة للقراءة فقط، مخصصة لمزامنة بيانات الخطوط.
router = APIRouter(
    prefix="/api/sync",
    tags=["App Sync"],
)

SCHEMA_VERSION = 2


def read_dataset_version(db: Session) -> int:
    version = db.execute(
        text("SELECT version FROM dataset_version WHERE id = 1")
    ).scalar()

    if version is None:
        raise HTTPException(
            status_code=500,
            detail="جدول dataset_version غير مهيأ",
        )

    return int(version)


def route_payload(route, coordinates, length_m) -> dict:
    lons = [point[0] for point in coordinates]
    lats = [point[1] for point in coordinates]

    price = route.bus.new_price

    return {
        "id": route.id,
        "bus_id": route.bus_id,
        "name": route.bus.name,
        "color": route.bus.color,
        "fare": float(price) if price is not None else None,
        "version": route.version,
        "direction": route.direction,
        "length_m": round(float(length_m), 1),
        "min_lon": min(lons),
        "min_lat": min(lats),
        "max_lon": max(lons),
        "max_lat": max(lats),
        "geometry": coordinates,
    }


def load_published_routes(db: Session) -> list[dict]:
    routes = (
        db.query(BusRoute)
        .join(BusRoute.bus)
        .options(joinedload(BusRoute.bus))
        .filter(
            BusRoute.is_active.is_(True),
            Bus.is_active.is_(True),
        )
        .order_by(BusRoute.bus_id, BusRoute.direction, BusRoute.id)
        .all()
    )

    if not routes:
        return []

    route_ids = [route.id for route in routes]

    geometry_rows = db.execute(
        text(
            """
            SELECT
                id,
                ST_AsGeoJSON(line_string, 6)::json AS geometry,
                ST_Length(line_string::geography) AS length_m
            FROM bus_route
            WHERE id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": route_ids},
    ).all()

    geometries = {row.id: row for row in geometry_rows}

    result = []

    for route in routes:
        geometry = geometries.get(route.id)

        if geometry is None or not geometry.geometry:
            continue

        coordinates = geometry.geometry.get("coordinates", [])

        if len(coordinates) < 2:
            continue

        result.append(
            route_payload(
                route,
                coordinates,
                geometry.length_m,
            )
        )

    return result


@router.get("/manifest")
def get_manifest(db: Session = Depends(get_db)):
    return {
        "data_version": read_dataset_version(db),
        "schema_version": SCHEMA_VERSION,
    }


@router.get("/routes")
def get_routes(db: Session = Depends(get_db)):
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
