from ninja.errors import HttpError
from ninja.security.session import SessionAuth as NinjaSessionAuth

from users.permissions import is_gym_staff


class SessionAuth(NinjaSessionAuth):
    """Cookie session auth. Inactive users are treated as anonymous."""

    def authenticate(self, request, key=None):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and getattr(user, "is_active", True):
            return user
        return None


# Frontend already sends X-CSRFToken. Django test Client still skips CSRF
# unless enforce_csrf_checks=True.
session_auth = SessionAuth(csrf=True)


class GymStaffAuth(SessionAuth):
    """Gym desk APIs: Reception, Admin, Super Admin, or is_staff — not gym members."""

    def authenticate(self, request, key=None):
        user = super().authenticate(request, key)
        if user is None:
            return None
        if not is_gym_staff(user):
            raise HttpError(403, "Staff access required.")
        return user


gym_staff_auth = GymStaffAuth(csrf=True)
