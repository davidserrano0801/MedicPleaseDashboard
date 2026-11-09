from django.conf import settings
from pymongo.errors import PyMongoError
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import APIException

from .mongo import get_users_collection
from .security import fingerprint, read_token


class AuthUser:
    """Usuario ya verificado; se expone como request.user."""
    is_authenticated = True

    def __init__(self, doc):
        self.username = doc["username"]
        self.role = doc["role"]


class DatabaseUnavailable(APIException):
    status_code = 503
    default_detail = "No se pudo consultar la base de datos"
    default_code = "database_unavailable"


class CookieAuthentication(BaseAuthentication):
    """Lee la sesión (cookie HttpOnly firmada) y confirma el usuario en MongoDB
    en cada petición, así un usuario desactivado, eliminado o con contraseña
    cambiada pierde el acceso de inmediato."""

    def authenticate(self, request):
        token = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        if not token:
            return None
        data = read_token(settings.SECRET_KEY, token)
        if not data:
            return None
        try:
            doc = get_users_collection().find_one({"username": data["u"]})
        except PyMongoError:
            raise DatabaseUnavailable()
        if not doc or not doc.get("active"):
            return None
        if fingerprint(doc["password_hash"]) != data.get("f"):
            return None
        return AuthUser(doc), token

    def authenticate_header(self, request):
        # Hace que "sin sesión" responda 401 (y no 403).
        return 'Cookie realm="plataforma"'
