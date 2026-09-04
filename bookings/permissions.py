"""Role and ownership checks for booking operations."""
from django.http import HttpRequest

from ninja_extra.permissions import BasePermission

from bookings.exceptions import PermissionDenied
from bookings.models import Booking
from users.models import UserRole
from users.permissions import get_user_role, is_admin, is_client, is_provider


class IsAuthenticatedUser(BasePermission):
    def has_permission(self, request: HttpRequest, controller) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated)


class IsAdminRole(BasePermission):
    message = "You do not have permission to modify this booking."

    def has_permission(self, request: HttpRequest, controller) -> bool:
        return is_admin(getattr(request, "user", None))


def assert_can_view_booking(user, booking: Booking) -> None:
    role = get_user_role(user)
    if role == UserRole.ADMIN:
        return
    if role == UserRole.PROVIDER and booking.provider_id == getattr(
        getattr(user, "provider_profile", None), "id", None
    ):
        return
    if role == UserRole.CLIENT and booking.client_id == getattr(
        getattr(user, "client_profile", None), "id", None
    ):
        return
    raise PermissionDenied("You do not have permission to view this booking.")


def assert_can_manage_booking(user, booking: Booking) -> None:
    role = get_user_role(user)
    if role == UserRole.ADMIN:
        return
    if role == UserRole.PROVIDER and booking.provider_id == getattr(
        getattr(user, "provider_profile", None), "id", None
    ):
        return
    raise PermissionDenied("You do not have permission to modify this booking.")


def assert_admin(user) -> None:
    if not is_admin(user):
        raise PermissionDenied("You do not have permission to perform this action.")


def can_record_payment(user, booking: Booking) -> bool:
    role = get_user_role(user)
    if role == UserRole.ADMIN:
        return True
    if role == UserRole.PROVIDER and booking.provider_id == getattr(
        getattr(user, "provider_profile", None), "id", None
    ):
        return True
    return False
