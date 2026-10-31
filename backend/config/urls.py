from django.urls import path
from api.views import (health, item_collection, item_detail,
                       save_upload, dashboard, player_detail)

urlpatterns = [
    path("api/health/", health, name="health"),
    path("api/items/", item_collection, name="item_collection"),
    path("api/items/<str:item_id>/", item_detail, name="item_detail"),
    path("api/saves/", save_upload, name="save_upload"),
    path("api/dashboard/", dashboard, name="dashboard"),
    path("api/players/<str:player_name>/", player_detail, name="player_detail"),
]
