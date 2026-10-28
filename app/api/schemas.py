
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Waypoint(BaseModel):
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


class BusFields(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    price: float = Field(ge=0)


class BusWithRouteCreateRequest(BusFields):
    direction: Literal["ذهاب", "إياب"]
    start_point: str = Field(min_length=1, max_length=150)
    end_point: str = Field(min_length=1, max_length=150)
    waypoints: list[Waypoint] = Field(min_length=2)


class BusWithRouteUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    price: float | None = Field(default=None, ge=0)

    direction: Literal["ذهاب", "إياب"]
    start_point: str = Field(min_length=1, max_length=150)
    end_point: str = Field(min_length=1, max_length=150)
    waypoints: list[Waypoint] = Field(min_length=2)


class BusRouteAddDirectionRequest(BaseModel):
    direction: Literal["ذهاب", "إياب"]
    start_point: str = Field(min_length=1, max_length=150)
    end_point: str = Field(min_length=1, max_length=150)
    waypoints: list[Waypoint] = Field(min_length=2)


class RoutePreviewRequest(BaseModel):
    waypoints: list[Waypoint] = Field(min_length=2)


class BRouterWaypointsRequest(BaseModel):
    waypoints: list[Waypoint] = Field(min_length=2)


class RouteSaveRequest(BaseModel):
    bus_id: int = Field(gt=0)
    direction: Literal["ذهاب", "إياب"]
    start_point: str = Field(min_length=1, max_length=150)
    end_point: str = Field(min_length=1, max_length=150)
    geometry: dict
    distance_m: float = Field(ge=0)
    trip_time_s: int = Field(ge=0)


class BusRouteResponse(BaseModel):
    id: int
    bus_id: int
    version: int
    direction: Literal["ذهاب", "إياب"]
    start_point: str
    end_point: str
    distance_m: float
    trip_time_s: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
