from rest_framework.permissions import BasePermission


class IsLoggedIn(BasePermission):
    """Cualquier usuario con sesión iniciada (administrador o profesor)."""
    def has_permission(self, request, view):
        return request.user is not None


class IsAdmin(BasePermission):
    """Solo el administrador."""
    def has_permission(self, request, view):
        return request.user is not None and request.user.role == "admin"
