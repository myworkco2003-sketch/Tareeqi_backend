from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Bus(Base):
    __tablename__ = "bus"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    new_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    routes: Mapped[list["BusRoute"]] = relationship(back_populates="bus")


class BusRoute(Base):
    __tablename__ = "bus_route"
    __table_args__ = (
        UniqueConstraint("bus_id", "direction", "version", name="uq_bus_route_version"),
        CheckConstraint("version >= 1", name="ck_bus_route_version_positive"),
        CheckConstraint(
            "trip_time IS NULL OR trip_time >= 0",
            name="ck_bus_route_trip_time_nonnegative",
        ),
        CheckConstraint(
            "distance IS NULL OR distance >= 0",
            name="ck_bus_route_distance_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bus_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("bus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    line_string = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326), nullable=False
    )
    distance: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Stored as whole minutes, as defined in the database schema.
    trip_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direction: Mapped[str] = mapped_column(String(50), nullable=False)
    start_point = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=True
    )
    end_point = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    bus: Mapped[Bus] = relationship(back_populates="routes")
