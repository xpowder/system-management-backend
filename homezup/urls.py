"""
URL configuration for homezup project.
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, re_path
from ninja_extra import NinjaExtraAPI

from core.views import frontend_asset, frontend_root_file, media_file, spa_index

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

api = NinjaExtraAPI(
    title="Homezup Booking API",
    description="Local booking management system API",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)


@api.exception_handler(BookingError)
def booking_error_handler(request, exc: BookingError):
    return api.create_response(
        request,
        {"error": exc.message, "detail": exc.message},
        status=exc.status_code,
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
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("media/<path:path>", media_file),
    path("assets/<path:path>", frontend_asset),
    path("favicon.svg", frontend_root_file, {"filename": "favicon.svg"}),
    re_path(r"^(?!api/|admin/|static/|media/).*$", spa_index),
]
