from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Bus(Base):
    __tablename__ = "bus"

    uniqueID: Mapped[int] = mapped_column(
        "uniqueID", BigInteger, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    oldPrice: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    newPrice: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    isActive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    routes: Mapped[list["BusRoute"]] = relationship(
        back_populates="bus", cascade="all, delete-orphan"
    )


class BusRoute(Base):
    __tablename__ = "bus_route"
    __table_args__ = (
        UniqueConstraint("busID", "direction", "version", name="uq_bus_route_version"),
        CheckConstraint("version >= 1", name="ck_bus_route_version_positive"),
        CheckConstraint('"tripTime" IS NULL OR "tripTime" >= 0', name="ck_bus_route_trip_time_nonnegative"),
        CheckConstraint("distance IS NULL OR distance >= 0", name="ck_bus_route_distance_nonnegative"),
    )

    uniqueID: Mapped[int] = mapped_column(
        "uniqueID", BigInteger, primary_key=True, autoincrement=True
    )
    busID: Mapped[int] = mapped_column(
        "busID",
        BigInteger,
        ForeignKey("bus.uniqueID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lineString = mapped_column(
        "lineString",
        Geometry(geometry_type="LINESTRING", srid=4326),
        nullable=False,
    )
    distance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tripTime: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direction: Mapped[str] = mapped_column(String(50), nullable=False)
    startPoint = mapped_column("startPoint", Geometry(geometry_type="POINT", srid=4326), nullable=True)
    endPoint = mapped_column("endPoint", Geometry(geometry_type="POINT", srid=4326), nullable=True)
    isActive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    bus: Mapped[Bus] = relationship(back_populates="routes")
