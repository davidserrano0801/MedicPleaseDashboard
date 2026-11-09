from django.urls import path
from api.views import (health, item_collection, item_detail, save_upload,
                       dashboard, player_detail, admin_export)
from api.user_views import login, logout, me, user_collection, user_detail

urlpatterns = [
    path("api/health/", health, name="health"),
    path("api/items/", item_collection, name="item_collection"),
    path("api/items/<str:item_id>/", item_detail, name="item_detail"),
    path("api/saves/", save_upload, name="save_upload"),
    path("api/dashboard/", dashboard, name="dashboard"),
    path("api/players/<str:player_name>/", player_detail, name="player_detail"),
    path("api/auth/login/", login, name="login"),
    path("api/auth/logout/", logout, name="logout"),
    path("api/auth/me/", me, name="me"),
    path("api/users/", user_collection, name="user_collection"),
    path("api/users/<str:username>/", user_detail, name="user_detail"),
    path("api/admin/export/", admin_export, name="admin_export"),
]
