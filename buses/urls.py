
from django.urls import path
from . import views

urlpatterns = [
    path("admin/routes", views.admin_routes_list, name="admin_routes"),
    path("admin/routes/", views.admin_routes_list, name="admin_routes_slash"),

    path("admin/routes/map", views.routes_map, name="admin_routes_map"),
    path("admin/routes/preview", views.preview_route, name="admin_routes_preview"),
    path("admin/routes/brouter-waypoints", views.preview_route, name="admin_routes_brouter_waypoints"),

    path("admin/routes/buses/<int:bus_id>/routes", views.add_direction, name="admin_bus_routes"),
    path("admin/routes/buses/<int:bus_id>", views.deactivate_bus, name="admin_deactivate_bus"),
    path("admin/routes/<int:route_id>", views.route_detail, name="admin_route_detail"),
]
