import hmac
from datetime import datetime, timezone
from django.conf import settings
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .mongo import get_client, get_collection, get_saves_collection
from .analytics import (ValidationError, validate_save, build_dashboard,
                        normalize_doc, stamp_attempts)
from .permissions import IsAdmin
from .user_views import public_user
from .mongo import get_users_collection

def serialize_item(document):
    return {
        "id": str(document["_id"]),
        "name": document.get("name", ""),
        "description": document.get("description", ""),
        "created_at": document.get("created_at").isoformat()
            if document.get("created_at") else None,
    }

@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
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
@permission_classes([IsAdmin])
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
@permission_classes([IsAdmin])
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
@authentication_classes([])
@permission_classes([AllowAny])
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
        saves = get_saves_collection()
        previous = saves.find_one({"playerName": data["playerName"]})
        fallback = previous["updated_at"].isoformat() if previous and previous.get("updated_at") else None
        stamp_attempts(data["caseHistory"], normalize_doc(previous) if previous else [], now, fallback)
        saves.update_one(
            {"playerName": data["playerName"]},
            {"$set": {**data, "updated_at": now},
             "$setOnInsert": {"created_at": now},
             "$unset": {"decisionsMade": "", "relevantDecisionsMade": "", "relevantDecisionMade": ""}},
            upsert=True,
        )
    except PyMongoError:
        return Response({"error": "No se pudo guardar la partida"},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)

    attempts = [a for c in data["caseHistory"] for a in c["attempts"]]
    return Response({"status": "ok", "playerName": data["playerName"],
                     "cases": len(data["caseHistory"]),
                     "attempts": len(attempts),
                     "decisions": sum(len(a["decisions"]) for a in attempts)},
                    status=status.HTTP_201_CREATED)

@api_view(["GET"])
def dashboard(request):
    try:
        saves = list(get_saves_collection().find().limit(5000))
    except PyMongoError:
        return Response({"error": "No se pudo consultar la base de datos"},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response(build_dashboard(saves))

@api_view(["GET", "DELETE"])
def player_detail(request, player_name):
    if request.method == "DELETE":
        if request.user.role != "admin":
            return Response({"error": "Solo el administrador puede eliminar jugadores"},
                            status=status.HTTP_403_FORBIDDEN)
        try:
            result = get_saves_collection().delete_one({"playerName": player_name})
        except PyMongoError:
            return Response({"error": "No se pudo eliminar al jugador"},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if result.deleted_count == 0:
            return Response({"error": "Jugador no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

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
        "caseHistory": normalize_doc(doc),
        "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
    })


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_export(request):
    """Copia completa de los datos (partidas y usuarios, sin contraseñas)."""
    try:
        saves = []
        for doc in get_saves_collection().find():
            doc.pop("_id", None)
            saves.append(doc)
        users = [public_user(d) for d in get_users_collection().find()]
    except PyMongoError:
        return Response({"error": "No se pudo consultar la base de datos"},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    now = datetime.now(timezone.utc)
    response = Response({"exported_at": now.isoformat(), "saves": saves, "users": users})
    response["Content-Disposition"] = f'attachment; filename="plataforma-{now:%Y%m%d-%H%M}.json"'
    return response
