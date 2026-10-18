from datetime import datetime

from app.db.database import Base
from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship



class MinibusRoute(Base):
    __tablename__ = "minibus_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    route_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    color: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
    )

    route_versions: Mapped[list["RouteVersion"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
    )

    route_fares: Mapped[list["RouteFare"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
    )


class RouteVersion(Base):
    __tablename__ = "route_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    route_id: Mapped[int] = mapped_column(
        ForeignKey("minibus_routes.id", ondelete="CASCADE"),
        nullable=False,
    )

    route: Mapped["MinibusRoute"] = relationship(
        back_populates="route_versions",
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    geom = mapped_column(
        Geometry(
            geometry_type="LINESTRING",
            srid=4326,
        ),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )



class RouteFare(Base):
    __tablename__ = "route_fares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    route_id: Mapped[int] = mapped_column(
        ForeignKey("minibus_routes.id", ondelete="CASCADE"),
        nullable=False,
    )

    fare: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    route: Mapped["MinibusRoute"] = relationship(
        back_populates="route_fares",
    )