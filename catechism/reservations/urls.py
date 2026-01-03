from django.urls import path
from . import views

urlpatterns = [
    # public
    path("view/", views.public_view, name="public_view"),
    path("api/public/grid", views.public_grid_api, name="public_grid_api"),

    # office
    path("", views.office_view, name="office_view"),
    path("office/", views.office_view, name="office_view"),
    path("office/rooms/", views.office_rooms_view, name="office_rooms_view"),
    path("office/rooms/<int:room_id>/", views.office_room_detail_view, name="office_room_detail_view"),
    path("api/office/grid", views.office_grid_api, name="office_grid_api"),
    path("api/office/reservations", views.office_create_reservation, name="office_create_reservation"),
    path("api/office/reservations/<int:rid>", views.office_update_reservation, name="office_update_reservation"),
    path("api/office/reservations/<int:rid>/cancel", views.office_cancel_reservation, name="office_cancel_reservation"),
]

