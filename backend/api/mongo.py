from functools import lru_cache
from pymongo import MongoClient
from django.conf import settings

@lru_cache(maxsize=1)
def get_client():
    cfg = settings.MONGO_CONFIG
    return MongoClient(
        host=cfg["host"],
        port=cfg["port"],
        username=cfg["username"],
        password=cfg["password"],
        authSource=cfg["database"],
        serverSelectionTimeoutMS=5000,
        tz_aware=True,  # las fechas vuelven con zona horaria (UTC)
    )

def get_collection():
    cfg = settings.MONGO_CONFIG
    return get_client()[cfg["database"]]["items"]

_saves_index_ready = False

def get_saves_collection():
    """Un documento por jugador (estado más reciente de su saveFile.json)."""
    global _saves_index_ready
    cfg = settings.MONGO_CONFIG
    collection = get_client()[cfg["database"]]["saves"]
    if not _saves_index_ready:
        collection.create_index("playerName", unique=True)
        _saves_index_ready = True
    return collection


_users_index_ready = False

def get_users_collection():
    """Usuarios de la plataforma (administrador y profesor)."""
    global _users_index_ready
    cfg = settings.MONGO_CONFIG
    collection = get_client()[cfg["database"]]["users"]
    if not _users_index_ready:
        collection.create_index("username", unique=True)
        _users_index_ready = True
    return collection
