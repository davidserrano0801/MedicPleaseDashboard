"""Inicio de sesión y administración de usuarios."""
import math
from datetime import datetime, timezone

from django.conf import settings
from pymongo.errors import DuplicateKeyError, PyMongoError
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .mongo import get_users_collection
from .permissions import IsAdmin
from .security import (InputError, LoginThrottle, dummy_hash, hash_password,
                       make_token, validate_password, validate_role,
                       validate_username, verify_password)

login_throttle = LoginThrottle()
_bootstrapped = False


def _db_error():
    return Response({"error": "No se pudo consultar la base de datos"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE)


def _client_ip(request):
    # Nginx fija X-Real-IP con la IP real del cliente.
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")


def public_user(doc):
    return {
        "username": doc["username"],
        "role": doc["role"],
        "active": bool(doc.get("active")),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        "created_by": doc.get("created_by"),
        "last_login": doc["last_login"].isoformat() if doc.get("last_login") else None,
    }


def new_user_doc(username, password, role, created_by):
    return {
        "username": username,
        "password_hash": hash_password(password),
        "role": role,
        "active": True,
        "created_at": datetime.now(timezone.utc),
        "created_by": created_by,
        "last_login": None,
    }


def bootstrap_admin(users):
    """Si no hay ningún administrador, crea el de ADMIN_USERNAME / ADMIN_PASSWORD (.env)."""
    global _bootstrapped
    if _bootstrapped:
        return
    if users.count_documents({"role": "admin"}, limit=1) == 0 and settings.ADMIN_PASSWORD:
        try:
            users.insert_one(new_user_doc(
                settings.ADMIN_USERNAME.strip().lower(), settings.ADMIN_PASSWORD, "admin", None))
        except DuplicateKeyError:
            pass
    _bootstrapped = True


# ------------------------------------------------------------------ sesión

@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login(request):
    data = request.data if isinstance(request.data, dict) else {}
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not isinstance(password, str) or not username or not password:
        return Response({"error": "Escribe usuario y contraseña"},
                        status=status.HTTP_400_BAD_REQUEST)
    username = username.strip().lower()

    key = f"{_client_ip(request)}|{username}"
    wait = login_throttle.blocked_for(key)
    if wait:
        response = Response(
            {"error": f"Demasiados intentos fallidos. Intenta de nuevo en {math.ceil(wait / 60)} min."},
            status=status.HTTP_429_TOO_MANY_REQUESTS)
        response["Retry-After"] = str(math.ceil(wait))
        return response

    try:
        users = get_users_collection()
        bootstrap_admin(users)
        doc = users.find_one({"username": username})
    except PyMongoError:
        return _db_error()

    valid = verify_password(password[:256], doc["password_hash"] if doc else dummy_hash())
    if not (doc and doc.get("active") and valid):
        login_throttle.fail(key)
        return Response({"error": "Usuario o contraseña incorrectos"},
                        status=status.HTTP_401_UNAUTHORIZED)

    login_throttle.reset(key)
    try:
        users.update_one({"_id": doc["_id"]}, {"$set": {"last_login": datetime.now(timezone.utc)}})
    except PyMongoError:
        pass  # no es crítico

    ttl = settings.AUTH_SESSION_HOURS * 3600
    response = Response({"username": doc["username"], "role": doc["role"]})
    response.set_cookie(
        settings.AUTH_COOKIE_NAME,
        make_token(settings.SECRET_KEY, doc["username"], doc["password_hash"], ttl),
        max_age=ttl, httponly=True, samesite="Lax",
        secure=settings.AUTH_COOKIE_SECURE, path="/",
    )
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def logout(request):
    response = Response({"status": "ok"})
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/", samesite="Lax")
    return response


@api_view(["GET"])
def me(request):
    return Response({"username": request.user.username, "role": request.user.role})


# ------------------------------------------------------ administrar usuarios

def _would_leave_without_admin(users, doc, new_role, new_active):
    """¿Este cambio dejaría el sistema sin ningún administrador activo?"""
    if not (doc["role"] == "admin" and doc.get("active")):
        return False
    if new_role == "admin" and new_active:
        return False
    return users.count_documents(
        {"role": "admin", "active": True, "username": {"$ne": doc["username"]}}, limit=1) == 0


@api_view(["GET", "POST"])
@permission_classes([IsAdmin])
def user_collection(request):
    try:
        users = get_users_collection()
        if request.method == "GET":
            return Response([public_user(d) for d in users.find().sort("created_at", 1)])
    except PyMongoError:
        return _db_error()

    data = request.data if isinstance(request.data, dict) else {}
    try:
        username = validate_username(data.get("username"))
        password = validate_password(data.get("password"))
        role = validate_role(data.get("role", "teacher"))
    except InputError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    doc = new_user_doc(username, password, role, request.user.username)
    try:
        users.insert_one(doc)
    except DuplicateKeyError:
        return Response({"error": "Ya existe un usuario con ese nombre"},
                        status=status.HTTP_409_CONFLICT)
    except PyMongoError:
        return _db_error()
    return Response(public_user(doc), status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAdmin])
def user_detail(request, username):
    username = username.strip().lower()
    is_self = username == request.user.username
    try:
        users = get_users_collection()
        doc = users.find_one({"username": username})
        if not doc:
            return Response({"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "DELETE":
            if is_self:
                return Response({"error": "No puedes eliminar tu propia cuenta"},
                                status=status.HTTP_400_BAD_REQUEST)
            if _would_leave_without_admin(users, doc, None, False):
                return Response({"error": "Debe quedar al menos un administrador activo"},
                                status=status.HTTP_400_BAD_REQUEST)
            users.delete_one({"_id": doc["_id"]})
            return Response(status=status.HTTP_204_NO_CONTENT)

        data = request.data if isinstance(request.data, dict) else {}
        updates = {}
        try:
            if "password" in data:
                updates["password_hash"] = hash_password(validate_password(data["password"]))
            if "role" in data:
                updates["role"] = validate_role(data["role"])
            if "active" in data:
                if not isinstance(data["active"], bool):
                    raise InputError("active debe ser true o false")
                updates["active"] = data["active"]
        except InputError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not updates:
            return Response({"error": "No hay nada que actualizar"},
                            status=status.HTTP_400_BAD_REQUEST)

        new_role = updates.get("role", doc["role"])
        new_active = updates.get("active", doc.get("active"))
        if is_self and not new_active:
            return Response({"error": "No puedes desactivar tu propia cuenta"},
                            status=status.HTTP_400_BAD_REQUEST)
        if _would_leave_without_admin(users, doc, new_role, new_active):
            return Response({"error": "Debe quedar al menos un administrador activo"},
                            status=status.HTTP_400_BAD_REQUEST)

        users.update_one({"_id": doc["_id"]}, {"$set": updates})
        return Response(public_user({**doc, **updates}))
    except PyMongoError:
        return _db_error()
