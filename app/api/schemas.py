from pydantic import BaseModel, Field


class Waypoint(BaseModel):
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


class RoutePreviewRequest(BaseModel):
    route_name: str = Field(min_length=1, max_length=100)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    fare: float = Field(ge=0)
    waypoints: list[Waypoint] = Field(min_length=2)


class BRouterWaypointsRequest(BaseModel):
    route_name: str = Field(min_length=1, max_length=100)
    waypoints: list[Waypoint] = Field(min_length=2)
    
class RouteSaveRequest(BaseModel):
    route_name: str = Field(min_length=1, max_length=100)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    fare: float = Field(ge=0)

    geometry: dict = Field(...)
