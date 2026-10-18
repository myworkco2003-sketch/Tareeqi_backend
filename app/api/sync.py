from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import MinibusRoute, RouteFare, RouteVersion

# مسارات عامة (للقراءة فقط) يستخدمها تطبيق الموبايل للمزامنة.
# منفصلة عن /admin/* ولا تعدّل أي شي.
router = APIRouter(
    prefix="/api/sync",
    tags=["App Sync"],
)

# إصدار مخطط قاعدة بيانات التطبيق (SQLite) اللي بيفهمه هالـ API
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


def route_payload(route, version, fare, coordinates, length_m) -> dict:
    lons = [point[0] for point in coordinates]
    lats = [point[1] for point in coordinates]

    return {
        "id": route.id,
        "name": route.route_name,
        "color": route.color,
        "fare": fare,
        "version": version.version,
        "length_m": round(length_m, 1),
        "min_lon": min(lons),
        "min_lat": min(lats),
        "max_lon": max(lons),
        "max_lat": max(lats),
        "geometry": coordinates,
    }


def load_published_routes(db: Session) -> list[dict]:
    routes = (
        db.query(MinibusRoute)
        .filter(MinibusRoute.is_active.is_(True))
        .order_by(MinibusRoute.id)
        .all()
    )

    if not routes:
        return []

    route_ids = [route.id for route in routes]

    # أحدث نسخة فعالة لكل خط
    versions: dict[int, RouteVersion] = {}
    active_versions = (
        db.query(RouteVersion)
        .filter(
            RouteVersion.route_id.in_(route_ids),
            RouteVersion.is_active.is_(True),
        )
        .order_by(RouteVersion.version.desc())
        .all()
    )
    for version in active_versions:
        versions.setdefault(version.route_id, version)

    if not versions:
        return []

    # هندسة كل النسخ باستعلام واحد (6 خانات عشرية = دقة حوالي 10 سم)
    geometry_rows = db.execute(
        text(
            """
            SELECT id,
                   ST_AsGeoJSON(geom, 6)::json AS g,
                   ST_Length(geom::geography) AS length_m
            FROM route_versions
            WHERE id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": [version.id for version in versions.values()]},
    ).all()
    geometries = {row.id: row for row in geometry_rows}

    # الأجرة الصالحة الأحدث لكل خط
    fares: dict[int, float] = {}
    valid_fares = (
        db.query(RouteFare)
        .filter(
            RouteFare.route_id.in_(route_ids),
            RouteFare.is_valid.is_(True),
        )
        .order_by(RouteFare.updated_at)
        .all()
    )
    for fare in valid_fares:
        fares[fare.route_id] = float(fare.fare)

    result = []

    for route in routes:
        version = versions.get(route.id)
        geometry = geometries.get(version.id) if version else None

        if geometry is None:
            continue

        result.append(
            route_payload(
                route,
                version,
                fares.get(route.id),
                geometry.g["coordinates"],
                float(geometry.length_m),
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
    # منقرأ رقم النسخة قبل وبعد قراءة الخطوط: إذا ما تغيّر، الخطوط
    # اللي قرأناها بالتأكيد تخص نفس النسخة (النشر بيغيّر الاثنين بعملية وحدة)
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