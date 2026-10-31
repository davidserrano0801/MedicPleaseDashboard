import hmac
from datetime import datetime, timezone
from django.conf import settings
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .mongo import get_client, get_collection, get_saves_collection
from .analytics import ValidationError, validate_save, build_dashboard

def serialize_item(document):
    return {
        "id": str(document["_id"]),
        "name": document.get("name", ""),
        "description": document.get("description", ""),
        "created_at": document.get("created_at").isoformat()
            if document.get("created_at") else None,
    }

@api_view(["GET"])
def health(request):
    try:
        get_client().admin.command("ping")
        return Response({"status": "ok", "database": "connected"})
    except PyMongoError:
        return Response(
            {"status": "error", "database": "disconnected"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

@api_view(["GET", "POST"])
def item_collection(request):
    collection = get_collection()

    if request.method == "GET":
        try:
            documents = collection.find().sort("created_at", -1).limit(100)
            return Response([serialize_item(doc) for doc in documents])
        except PyMongoError:
            return Response({"error": "No se pudieron consultar los elementos"},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

    name = str(request.data.get("name", "")).strip()
    description = str(request.data.get("description", "")).strip()

    if not name:
        return Response({"error": "El campo name es obligatorio"},
                         status=status.HTTP_400_BAD_REQUEST)

    document = {
        "name": name[:120],
        "description": description[:2000],
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = collection.insert_one(document)
        document["_id"] = result.inserted_id
        return Response(serialize_item(document), status=status.HTTP_201_CREATED)
    except PyMongoError:
        return Response({"error": "No se pudo guardar el elemento"},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)

@api_view(["DELETE"])
def item_detail(request, item_id):
    try:
        object_id = ObjectId(item_id)
    except (InvalidId, TypeError):
        return Response({"error": "Identificador inválido"},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        result = get_collection().delete_one({"_id": object_id})
        if result.deleted_count == 0:
            return Response({"error": "Elemento no encontrado"},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
    except PyMongoError:
        return Response({"error": "No se pudo eliminar el elemento"},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)


# ------------------------------------------------------------------ juego

def _has_valid_api_key(request):
    expected = settings.GAME_API_KEY
    provided = request.headers.get("X-API-Key", "")
    return bool(expected) and hmac.compare_digest(provided, expected)

@api_view(["POST"])
def save_upload(request):
    """Unity envía aquí el contenido de saveFile.json (requiere X-API-Key)."""
    if not _has_valid_api_key(request):
        return Response({"error": "API key inválida"}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        data = validate_save(request.data)
    except ValidationError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    now = datetime.now(timezone.utc)
    try:
        get_saves_collection().update_one(
            {"playerName": data["playerName"]},
            {"$set": {**data, "updated_at": now},
             "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    except PyMongoError:
        return Response({"error": "No se pudo guardar la partida"},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response({"status": "ok", "playerName": data["playerName"],
                     "decisions": len(data["decisionsMade"])},
                    status=status.HTTP_201_CREATED)

@api_view(["GET"])
def dashboard(request):
    try:
        saves = list(get_saves_collection().find().limit(5000))
    except PyMongoError:
        return Response({"error": "No se pudo consultar la base de datos"},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response(build_dashboard(saves))

@api_view(["GET"])
def player_detail(request, player_name):
    try:
        doc = get_saves_collection().find_one({"playerName": player_name})
    except PyMongoError:
        return Response({"error": "No se pudo consultar la base de datos"},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    if not doc:
        return Response({"error": "Jugador no encontrado"}, status=status.HTTP_404_NOT_FOUND)
    return Response({
        "playerName": doc["playerName"],
        "actualCase": doc.get("actualCase", ""),
        "decisionsMade": doc.get("decisionsMade", []),
        "relevantDecisionsMade": doc.get("relevantDecisionsMade"),
        "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
    })
