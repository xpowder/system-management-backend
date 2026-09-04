"""
URL configuration for homezup project.
"""
import logging

from django.conf import settings
from django.contrib import admin
from django.urls import path, re_path
from ninja.errors import HttpError
from ninja_extra import NinjaExtraAPI

from core.views import (
    api_home,
    frontend_asset,
    frontend_root_file,
    healthz,
    media_file,
    spa_index,
)

from bookings.controllers import (
    AuthController,
    BookingController,
    ClientBookingController,
    DashboardReportController,
    PropertyAvailabilityController,
)
from bookings.exceptions import BookingError
from fitness.controllers import router as fitness_router
from users.controllers import router as users_router

logger = logging.getLogger("flexoper.request")

api = NinjaExtraAPI(
    title="FlexOper API",
    description="Gym desk API for members, memberships, payments, and attendance.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)


@api.exception_handler(BookingError)
def booking_error_handler(request, exc: BookingError):
    return api.create_response(
        request,
        {"error": exc.message, "detail": exc.message},
        status=exc.status_code,
    )


@api.exception_handler(Exception)
def unhandled_api_error(request, exc: Exception):
    if isinstance(exc, HttpError):
        return api.create_response(request, {"detail": str(exc)}, status=exc.status_code)
    if isinstance(exc, BookingError):
        return booking_error_handler(request, exc)
    logger.exception("Unhandled API exception")
    return api.create_response(
        request,
        {"detail": "Internal server error."},
        status=500,
    )


api.register_controllers(
    AuthController,
    BookingController,
    DashboardReportController,
    PropertyAvailabilityController,
    ClientBookingController,
)
api.add_router("", users_router)
api.add_router("", fitness_router)

urlpatterns = [
    path("", api_home),
    path("healthz", healthz),
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("media/<path:path>", media_file),
]
if getattr(settings, "SERVE_FRONTEND", False):
    urlpatterns += [
        path("assets/<path:path>", frontend_asset),
        path("favicon.svg", frontend_root_file, {"filename": "favicon.svg"}),
        re_path(r"^(?!api/|admin/|static/|media/|healthz).*$", spa_index),
    ]
