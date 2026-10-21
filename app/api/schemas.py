from pydantic import BaseModel, Field, model_validator


class Waypoint(BaseModel):
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


class RoutePreviewRequest(BaseModel):
    route_name: str | None = Field(default=None, min_length=1, max_length=150)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    fare: float | None = Field(default=None, ge=0)
    old_price: float | None = Field(default=None, ge=0)
    new_price: float | None = Field(default=None, ge=0)
    direction: str = Field(default="forward", min_length=1, max_length=50)
    waypoints: list[Waypoint] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_name(self):
        if not (self.name or self.route_name):
            raise ValueError("name or route_name is required")
        return self


class BRouterWaypointsRequest(BaseModel):
    route_name: str | None = Field(default=None, min_length=1, max_length=150)
    waypoints: list[Waypoint] = Field(min_length=2)


class RouteSaveRequest(BaseModel):
    # New dashboard fields
    bus_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    old_price: float | None = Field(default=None, ge=0)
    new_price: float | None = Field(default=None, ge=0)
    direction: str = Field(default="forward", min_length=1, max_length=50)
    is_active: bool = True

    # Values returned by BRouter (geometry is required for a save)
    geometry: dict
    distance_m: float | None = Field(default=None, ge=0)
    duration_minutes: float | None = Field(default=None, ge=0)
    start_point: Waypoint | None = None
    end_point: Waypoint | None = None

    # Temporary backwards compatibility with the current dashboard
    route_name: str | None = Field(default=None, min_length=1, max_length=150)
    fare: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_name_and_price(self):
        if not (self.name or self.route_name):
            raise ValueError("name or route_name is required")
        if self.new_price is None and self.fare is None:
            raise ValueError("new_price is required")
        if self.geometry.get("type") != "LineString":
            raise ValueError("geometry must be a GeoJSON LineString")
        coordinates = self.geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            raise ValueError("LineString must contain at least two coordinates")
        for point in coordinates:
            if (
                not isinstance(point, (list, tuple))
                or len(point) < 2
                or not isinstance(point[0], (int, float))
                or not isinstance(point[1], (int, float))
                or not -180 <= point[0] <= 180
                or not -90 <= point[1] <= 90
            ):
                raise ValueError("LineString contains invalid longitude/latitude coordinates")
        return self
