"""Seguridad de usuarios: contraseñas, sesiones firmadas y límite de intentos.

Solo usa la librería estándar (no depende de Django ni de MongoDB), así que se
puede probar de forma aislada.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time

ROLES = ("admin", "teacher")
ROLE_LABELS = {"admin": "Administrador", "teacher": "Profesor"}

PBKDF2_ITERATIONS = 600_000
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,40}$")
MIN_PASSWORD = 8
MAX_PASSWORD = 128


class InputError(ValueError):
    """Dato de entrada inválido (se responde con 400)."""


# ------------------------------------------------------------ validaciones

def normalize_username(value):
    if not isinstance(value, str):
        raise InputError("El usuario debe ser texto")
    return value.strip().lower()


def validate_username(value):
    username = normalize_username(value)
    if not USERNAME_RE.match(username):
        raise InputError(
            "El usuario debe tener entre 3 y 40 caracteres: letras, números, punto, guion o guion bajo"
        )
    return username


def validate_password(value):
    if not isinstance(value, str):
        raise InputError("La contraseña debe ser texto")
    if len(value) < MIN_PASSWORD:
        raise InputError(f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres")
    if len(value) > MAX_PASSWORD:
        raise InputError(f"La contraseña no puede superar {MAX_PASSWORD} caracteres")
    return value


def validate_role(value):
    if value not in ROLES:
        raise InputError("El rol debe ser 'admin' (administrador) o 'teacher' (profesor)")
    return value


# ---------------------------------------------------------- contraseñas

def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password, salt=None, iterations=PBKDF2_ITERATIONS):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64(salt)}${_b64(digest)}"


def verify_password(password, stored):
    """Compara en tiempo constante. Nunca lanza excepciones por datos raros."""
    try:
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _unb64(salt), int(iterations)
        )
        return hmac.compare_digest(_b64(digest), expected)
    except (ValueError, AttributeError, TypeError):
        return False


_dummy = None


def dummy_hash():
    """Hash de relleno: se verifica igual cuando el usuario no existe, para que
    la respuesta tarde lo mismo y no se pueda averiguar qué usuarios existen."""
    global _dummy
    if _dummy is None:
        _dummy = hash_password("contraseña-de-relleno")
    return _dummy


# ------------------------------------------------------------- sesiones

def fingerprint(password_hash):
    """Cambia cuando se cambia la contraseña: invalida las sesiones anteriores."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def _key(secret):
    return hmac.new(secret.encode(), b"plataforma.sesion", hashlib.sha256).digest()


def make_token(secret, username, password_hash, ttl_seconds, now=None):
    now = time.time() if now is None else now
    payload = _b64(json.dumps(
        {"u": username, "f": fingerprint(password_hash), "exp": int(now + ttl_seconds)},
        separators=(",", ":"),
    ).encode())
    signature = _b64(hmac.new(_key(secret), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def read_token(secret, token, now=None):
    """Devuelve {'u','f','exp'} si la firma es válida y no ha expirado; si no, None."""
    now = time.time() if now is None else now
    try:
        payload, signature = token.split(".")
        expected = _b64(hmac.new(_key(secret), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(_unb64(payload))
        if not isinstance(data, dict) or data.get("exp", 0) < now or "u" not in data:
            return None
        return data
    except (ValueError, AttributeError, TypeError, UnicodeDecodeError):
        return None


# ----------------------------------------------------- límite de intentos

class LoginThrottle:
    """Bloquea una clave (IP + usuario) tras varios intentos fallidos seguidos.
    Vive en memoria de cada proceso del servidor (es un freno, no una garantía)."""

    def __init__(self, max_failures=5, window=300, lock=300):
        self.max_failures = max_failures
        self.window = window
        self.lock = lock
        self._state = {}
        self._mutex = threading.Lock()

    def blocked_for(self, key, now=None):
        now = time.time() if now is None else now
        with self._mutex:
            entry = self._state.get(key)
            if entry and entry["locked_until"] > now:
                return entry["locked_until"] - now
            return 0

    def fail(self, key, now=None):
        now = time.time() if now is None else now
        with self._mutex:
            if len(self._state) > 10000:
                self._state = {k: v for k, v in self._state.items()
                               if v["locked_until"] > now or v["fails"]}
            entry = self._state.setdefault(key, {"fails": [], "locked_until": 0})
            entry["fails"] = [t for t in entry["fails"] if now - t < self.window] + [now]
            if len(entry["fails"]) >= self.max_failures:
                entry["locked_until"] = now + self.lock
                entry["fails"] = []

    def reset(self, key):
        with self._mutex:
            self._state.pop(key, None)
