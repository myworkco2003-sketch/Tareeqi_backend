from pydantic import BaseModel, Field, model_validator


class Waypoint(BaseModel):
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


class BusCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    color: str | None = Field(default=None, max_length=30)
    old_price: float | None = Field(default=None, ge=0)
    new_price: float | None = Field(default=None, ge=0)
    is_active: bool = True


class BusUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    color: str | None = Field(default=None, max_length=30)
    old_price: float | None = Field(default=None, ge=0)
    new_price: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class BRouterWaypointsRequest(BaseModel):
    route_name: str | None = Field(default=None, min_length=1, max_length=150)
    waypoints: list[Waypoint] = Field(min_length=2)


class RoutePreviewRequest(BaseModel):
    waypoints: list[Waypoint] = Field(min_length=2)


class RouteSaveRequest(BaseModel):
    bus_id: int = Field(gt=0)
    direction: str = Field(min_length=1, max_length=50)
    is_active: bool = True
    geometry: dict
    distance: float = Field(ge=0)
    trip_time: float = Field(ge=0)
    start_point: Waypoint | None = None
    end_point: Waypoint | None = None

    @model_validator(mode="after")
    def validate_linestring(self):
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
