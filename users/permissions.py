"""Role helpers for the existing Django User + profile model."""
from django.contrib.auth.models import User

from users.models import UserRole


def get_user_role(user: User) -> str | None:
    if not user or not user.is_authenticated:
        return None
    group = user.groups.first()
    if group:
        return group.name
    if user.is_staff or user.is_superuser:
        return UserRole.ADMIN
    if hasattr(user, "provider_profile"):
        return UserRole.PROVIDER
    if hasattr(user, "client_profile"):
        return UserRole.CLIENT
    return None


def is_admin(user: User) -> bool:
    return (get_user_role(user) or '').lower().replace(' ', '') in ('admin', 'superadmin')


def is_provider(user: User) -> bool:
    return (get_user_role(user) or '').lower() in (UserRole.PROVIDER, 'trainer')


def is_client(user: User) -> bool:
    return (get_user_role(user) or '').lower() == UserRole.CLIENT


GYM_STAFF_GROUPS = ('Admin', 'Super Admin', 'Reception')
ALLOWED_STAFF_ROLES = ('Reception', 'Trainer', 'Admin', 'Super Admin')


def is_gym_staff(user: User) -> bool:
    """Desk staff who may use FlexOper gym APIs. Gym members and providers cannot."""
    if not user or not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', True):
        return False
    if user.is_superuser or user.is_staff:
        return True
    group = user.groups.first()
    return bool(group and group.name in GYM_STAFF_GROUPS)
