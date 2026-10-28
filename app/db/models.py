
from datetime import datetime, timezone
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Bus(Base):
    __tablename__ = "bus"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False)

    old_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    new_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    routes: Mapped[list["BusRoute"]] = relationship(
        back_populates="bus",
        passive_deletes=True,
    )


class BusRoute(Base):
    __tablename__ = "bus_route"

    __table_args__ = (
        UniqueConstraint(
            "bus_id",
            "direction",
            "version",
            name="bus_route_bus_id_direction_version_key",
        ),
        CheckConstraint("version >= 1", name="bus_route_version_check"),
        CheckConstraint(
            "direction IN ('ذهاب', 'إياب')",
            name="bus_route_direction_check",
        ),
        CheckConstraint("distance_m >= 0", name="bus_route_distance_m_check"),
        CheckConstraint(
            "trip_time_s >= 0",
            name="bus_route_trip_time_s_check",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    bus_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("bus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    line_string: Mapped[object] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326),
        nullable=False,
    )

    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    trip_time_s: Mapped[int] = mapped_column(Integer, nullable=False)

    direction: Mapped[str] = mapped_column(String(4), nullable=False)
    start_point: Mapped[str] = mapped_column(String(150), nullable=False)
    end_point: Mapped[str] = mapped_column(String(150), nullable=False)

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    bus: Mapped["Bus"] = relationship(back_populates="routes")
