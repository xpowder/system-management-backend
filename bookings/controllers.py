"""Django Ninja Extra controllers for local booking management."""
import re
from datetime import date
from decimal import Decimal
from typing import List, Optional

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from ninja.errors import HttpError
from ninja_extra import ControllerBase, api_controller, http_get, http_patch, http_post

from core.auth import session_auth
from core.lockout import clear_account_failures, is_blocked, record_failure
from core.sessions import flush_user_sessions
from bookings.exceptions import BookingError
from bookings.exports import (
    export_bookings_csv,
    export_outstanding_csv,
    export_payments_csv,
    export_revenue_csv,
)
from bookings.models import Booking, BookingPayment
from bookings.permissions import (
    IsAuthenticatedUser,
    assert_admin,
    assert_can_manage_booking,
    assert_can_view_booking,
    can_record_payment,
)
from bookings.receipts import receipt_html_response, receipt_pdf_response
from bookings.schemas import (
    AvailabilityOut,
    BookingApproveIn,
    BookingCancelIn,
    BookingIn,
    BookingOut,
    BookingPaymentIn,
    BookingPaymentOut,
    BookingPreviewOut,
    BookingRejectIn,
    DashboardOut,
    ErrorOut,
    MonthlyRevenueOut,
    OccupancyOut,
    OutstandingPaymentOut,
    ReceiptOut,
)
from bookings.selectors import (
    apply_user_scope,
    get_booking_by_id,
    get_booking_payments,
    get_bookings,
    get_client_bookings,
    get_dashboard,
    get_monthly_revenue,
    get_occupied_properties,
    get_outstanding_payments,
    get_property_availability_calendar,
    get_property_bookings,
)
from bookings.services import (
    approve_booking,
    calculate_booking_months,
    calculate_booking_price,
    cancel_booking,
    check_property_availability,
    create_booking,
    record_cash_payment,
    reject_booking,
    update_booking_statuses,
)
from users.models import ClientProfile, Property, ProviderProfile
from users.passwords import require_strong_password
from users.permissions import can_access_property, is_admin
from users.schemas import AccountProfileUpdateIn, LoginIn, MeOut, PasswordChangeIn
from users.models import StaffProfile


ERROR_RESPONSE = {400: ErrorOut, 403: ErrorOut, 404: ErrorOut}


_IP_RE = re.compile(r"^[0-9a-fA-F.:]{3,45}$")


def _client_ip(request):
    """Use the original client IP on Railway; ignore spoofed X-Forwarded-For locally."""
    candidates = []
    trust_proxy = bool(getattr(settings, "USE_HTTPS", False) or getattr(settings, "ON_RAILWAY", False))
    if trust_proxy:
        forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
        if forwarded:
            candidates.append(forwarded)
    candidates.append(request.META.get("REMOTE_ADDR") or "")
    for value in candidates:
        if value and _IP_RE.match(value):
            return value
    return "unknown"


def _http_error(exc: BookingError) -> None:
    raise HttpError(exc.status_code, exc.message)


def _get_booking_or_404(booking_id: int) -> Booking:
    booking = get_booking_by_id(booking_id)
    if not booking:
        raise HttpError(404, "Booking not found.")
    return booking


@api_controller("/auth", tags=["Auth"])
class AuthController(ControllerBase):
    # Login/logout stay CSRF-exempt on purpose: they use auth=None to bootstrap
    # (or tear down) the Django session cookie. Ninja cookie CSRF only runs on
    # session_auth / gym_staff_auth. Requiring X-CSRFToken here would break the
    # existing SPA, which POSTs /api/auth/login without that header.
    @http_post("/login", response={200: MeOut, 401: ErrorOut, 429: ErrorOut}, auth=None)
    def login_view(self, payload: LoginIn):
        request = self.context.request
        ip = _client_ip(request)
        if is_blocked(ip, payload.username):
            raise HttpError(429, "Too many login attempts. Try again later.")
        user = authenticate(
            request,
            username=payload.username,
            password=payload.password,
        )
        if not user:
            record_failure(ip, payload.username)
            if is_blocked(ip, payload.username):
                raise HttpError(429, "Too many login attempts. Try again later.")
            raise HttpError(401, "Invalid username or password.")
        clear_account_failures(ip, payload.username)
        login(request, user)
        return MeOut.from_user(user)


    @http_post("/logout", auth=None)
    def logout_view(self):
        request = self.context.request
        logout(request)
        request.session.flush()
        return {"ok": True}

    @http_get("/me", response=MeOut, auth=session_auth)
    def me(self):
        return MeOut.from_user(self.context.request.user)

    @http_patch("/profile", response=MeOut, auth=session_auth)
    def update_profile(self, payload: AccountProfileUpdateIn):
        user = self.context.request.user
        user.first_name = payload.first_name
        user.last_name = payload.last_name
        user.email = payload.email
        user.save(update_fields=['first_name', 'last_name', 'email', 'updated_at'] if hasattr(user, 'updated_at') else ['first_name', 'last_name', 'email'])
        StaffProfile.objects.update_or_create(user=user, defaults={'phone': payload.phone})
        return MeOut.from_user(user)

    @http_post("/password", response={200: MeOut, 400: ErrorOut}, auth=session_auth)
    def change_password(self, payload: PasswordChangeIn):
        user = self.context.request.user
        if not user.check_password(payload.current_password):
            raise HttpError(400, 'Current password is incorrect.')
        require_strong_password(payload.new_password, user=user)
        user.set_password(payload.new_password)
        user.save(update_fields=['password'])
        request = self.context.request
        update_session_auth_hash(request, user)
        flush_user_sessions(user, keep_session_key=request.session.session_key)
        return MeOut.from_user(user)


@api_controller(
    "/bookings",
    tags=["Bookings"],
    auth=session_auth,
    permissions=[IsAuthenticatedUser],
)
class BookingController(ControllerBase):
    @http_post(
        "",
        response={200: BookingOut, **ERROR_RESPONSE},
    )
    def create(self, payload: BookingIn):
        assert_admin(self.context.request.user)
        property_id = payload.property_id or payload.property_ref_id
        if not property_id:
            raise HttpError(400, "Invalid property.")
        try:
            client = ClientProfile.objects.get(id=payload.client_id)
            property_obj = Property.objects.select_related("provider").get(id=property_id)
            booking = create_booking(
                client=client,
                property_obj=property_obj,
                start_date=payload.start_date,
                end_date=payload.end_date,
                notes=payload.notes or "",
                provider=None
                if payload.provider_id is None
                else ProviderProfile.objects.filter(id=payload.provider_id).first(),
            )
            return booking
        except ClientProfile.DoesNotExist:
            raise HttpError(400, "Invalid client.")
        except Property.DoesNotExist:
            raise HttpError(400, "Invalid property.")
        except BookingError as exc:
            _http_error(exc)

    @http_get("", response=List[BookingOut])
    def list_bookings(
        self,
        status: Optional[str] = None,
        payment_status: Optional[str] = None,
        client_id: Optional[int] = None,
        property_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        search: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        client = None
        property_obj = None
        provider = None
        if client_id:
            client = ClientProfile.objects.filter(id=client_id).first()
        if property_id:
            property_obj = Property.objects.filter(id=property_id).first()
        if provider_id:
            provider = ProviderProfile.objects.filter(id=provider_id).first()

        queryset = apply_user_scope(
            get_bookings(
                status=status,
                payment_status=payment_status,
                client=client,
                property_obj=property_obj,
                provider=provider,
                search=search,
                start_date=start_date,
                end_date=end_date,
            ),
            self.context.request.user,
        )
        return list(queryset[offset : offset + limit])

    @http_get("/{int:booking_id}", response={200: BookingOut, **ERROR_RESPONSE})
    def retrieve(self, booking_id: int):
        booking = _get_booking_or_404(booking_id)
        try:
            assert_can_view_booking(self.context.request.user, booking)
        except BookingError as exc:
            _http_error(exc)
        return booking

    @http_post("/{int:booking_id}/approve", response={200: BookingOut, **ERROR_RESPONSE})
    def approve(self, booking_id: int, payload: BookingApproveIn):
        booking = _get_booking_or_404(booking_id)
        try:
            assert_can_manage_booking(self.context.request.user, booking)
            return approve_booking(booking, notes=payload.notes or "")
        except BookingError as exc:
            _http_error(exc)

    @http_post("/{int:booking_id}/reject", response={200: BookingOut, **ERROR_RESPONSE})
    def reject(self, booking_id: int, payload: BookingRejectIn):
        booking = _get_booking_or_404(booking_id)
        try:
            assert_can_manage_booking(self.context.request.user, booking)
            return reject_booking(booking, notes=payload.notes or "")
        except BookingError as exc:
            _http_error(exc)

    @http_post("/{int:booking_id}/cancel", response={200: BookingOut, **ERROR_RESPONSE})
    def cancel(self, booking_id: int, payload: BookingCancelIn):
        booking = _get_booking_or_404(booking_id)
        try:
            assert_can_manage_booking(self.context.request.user, booking)
            return cancel_booking(booking, notes=payload.notes or "")
        except BookingError as exc:
            _http_error(exc)

    @http_get(
        "/{int:booking_id}/payments",
        response={200: List[BookingPaymentOut], **ERROR_RESPONSE},
    )
    def payments(self, booking_id: int):
        booking = _get_booking_or_404(booking_id)
        try:
            assert_can_view_booking(self.context.request.user, booking)
        except BookingError as exc:
            _http_error(exc)
        return list(get_booking_payments(booking))

    @http_post(
        "/{int:booking_id}/payments",
        response={200: BookingPaymentOut, **ERROR_RESPONSE},
    )
    def record_payment(self, booking_id: int, payload: BookingPaymentIn):
        booking = _get_booking_or_404(booking_id)
        user = self.context.request.user
        if not can_record_payment(user, booking):
            raise HttpError(403, "You do not have permission to modify this booking.")
        try:
            return record_cash_payment(
                booking=booking,
                amount=payload.amount,
                received_by_user=payload.received_by_user or "",
                receipt_number=payload.receipt_number or "",
                notes=payload.notes or "",
                received_by=user,
            )
        except BookingError as exc:
            _http_error(exc)

    @http_get("/{int:booking_id}/payments/{int:payment_id}/receipt")
    def payment_receipt_pdf(self, booking_id: int, payment_id: int):
        booking = _get_booking_or_404(booking_id)
        try:
            assert_can_view_booking(self.context.request.user, booking)
            payment = booking.payments.get(id=payment_id)
        except BookingPayment.DoesNotExist:
            raise HttpError(404, "Payment not found.")
        except BookingError as exc:
            _http_error(exc)
        return receipt_pdf_response(payment)

    @http_get("/{int:booking_id}/payments/{int:payment_id}/receipt.html")
    def payment_receipt_html(self, booking_id: int, payment_id: int):
        booking = _get_booking_or_404(booking_id)
        try:
            assert_can_view_booking(self.context.request.user, booking)
            payment = booking.payments.get(id=payment_id)
        except BookingPayment.DoesNotExist:
            raise HttpError(404, "Payment not found.")
        except BookingError as exc:
            _http_error(exc)
        return receipt_html_response(payment)

    @http_get("/{int:booking_id}/payments/{int:payment_id}/receipt.json", response=ReceiptOut)
    def payment_receipt_json(self, booking_id: int, payment_id: int):
        from bookings.receipts import receipt_context

        booking = _get_booking_or_404(booking_id)
        try:
            assert_can_view_booking(self.context.request.user, booking)
            payment = booking.payments.get(id=payment_id)
        except BookingPayment.DoesNotExist:
            raise HttpError(404, "Payment not found.")
        except BookingError as exc:
            _http_error(exc)
        return receipt_context(payment)


@api_controller("", tags=["Dashboard"], auth=session_auth, permissions=[IsAuthenticatedUser])
class DashboardReportController(ControllerBase):
    @http_get("/dashboard", response=DashboardOut)
    def dashboard(self):
        assert_admin(self.context.request.user)
        return get_dashboard()

    @http_get("/reports/revenue", response=MonthlyRevenueOut)
    def revenue(self, year: Optional[int] = None, month: Optional[int] = None):
        assert_admin(self.context.request.user)
        today = date.today()
        year = year or today.year
        month = month or today.month
        return {
            "year": year,
            "month": month,
            "month_label": date(year, month, 1).strftime("%B %Y"),
            "cash_collected": get_monthly_revenue(year, month),
            "currency": "MAD",
        }

    @http_get("/reports/outstanding", response=List[OutstandingPaymentOut])
    def outstanding(self):
        assert_admin(self.context.request.user)
        return [
            {
                "client_name": f"{booking.client.user.first_name} {booking.client.user.last_name}",
                "booking_id": booking.id,
                "remaining_balance": booking.remaining_balance,
                "due_date": booking.end_date,
            }
            for booking in get_outstanding_payments()
        ]

    @http_get("/reports/occupancy", response=OccupancyOut)
    def occupancy(self):
        assert_admin(self.context.request.user)
        from users.models import Property as PropertyModel

        total = PropertyModel.objects.filter(is_active=True).count()
        occupied = get_occupied_properties()
        available = total - occupied
        rate = (
            (Decimal(occupied) / Decimal(total) * Decimal("100")).quantize(Decimal("0.01"))
            if total
            else Decimal("0.00")
        )
        return {
            "total_properties": total,
            "occupied": occupied,
            "available": available,
            "occupancy_rate": rate,
        }

    @http_get("/exports/bookings.csv")
    def export_bookings(self):
        assert_admin(self.context.request.user)
        return export_bookings_csv()

    @http_get("/exports/payments.csv")
    def export_payments(self):
        assert_admin(self.context.request.user)
        return export_payments_csv()

    @http_get("/exports/outstanding.csv")
    def export_outstanding(self):
        assert_admin(self.context.request.user)
        return export_outstanding_csv()

    @http_get("/exports/revenue.csv")
    def export_revenue(self, year: Optional[int] = None, month: Optional[int] = None):
        assert_admin(self.context.request.user)
        today = date.today()
        return export_revenue_csv(year or today.year, month or today.month)

    @http_post("/management/update-statuses")
    def trigger_status_update(self):
        assert_admin(self.context.request.user)
        return update_booking_statuses()


@api_controller("/properties", tags=["Properties"], auth=session_auth, permissions=[IsAuthenticatedUser])
class PropertyAvailabilityController(ControllerBase):
    @http_get("/{int:property_id}/availability", response={200: AvailabilityOut, **ERROR_RESPONSE})
    def availability(
        self,
        property_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ):
        try:
            property_obj = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            raise HttpError(404, "Property not found.")
        if not can_access_property(self.context.request.user, property_obj):
            raise HttpError(403, "You do not have permission to access this property.")

        today = date.today()
        start = start_date or today.replace(day=1)
        if end_date:
            end = end_date
        else:
            if start.month == 12:
                end = date(start.year + 1, 1, 1)
            else:
                end = date(start.year, start.month + 1, 1)

        try:
            is_available = check_property_availability(property_obj, start, end)
        except BookingError as exc:
            _http_error(exc)

        return {
            "property_id": property_obj.id,
            "start_date": start,
            "end_date": end,
            "available": is_available,
            "intervals": get_property_availability_calendar(property_obj, start, end),
        }

    @http_get("/{int:property_id}/bookings", response=List[BookingOut])
    def property_bookings(self, property_id: int):
        try:
            property_obj = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            raise HttpError(404, "Property not found.")
        if not can_access_property(self.context.request.user, property_obj):
            raise HttpError(403, "You do not have permission to access this property.")
        queryset = apply_user_scope(
            get_property_bookings(property_obj),
            self.context.request.user,
        )
        return list(queryset)

    @http_get("/{int:property_id}/preview", response={200: BookingPreviewOut, **ERROR_RESPONSE})
    def preview(self, property_id: int, start_date: date, end_date: date):
        try:
            property_obj = Property.objects.get(id=property_id)
            if not can_access_property(self.context.request.user, property_obj):
                raise HttpError(403, "You do not have permission to access this property.")
            months = calculate_booking_months(start_date, end_date)
            total = calculate_booking_price(property_obj.monthly_price, months)
            return {
                "months": months,
                "monthly_price": property_obj.monthly_price,
                "total_price": total,
                "payment_method": "cash",
                "currency": "MAD",
            }
        except Property.DoesNotExist:
            raise HttpError(404, "Property not found.")
        except BookingError as exc:
            _http_error(exc)


@api_controller("/clients", tags=["Clients"], auth=session_auth, permissions=[IsAuthenticatedUser])
class ClientBookingController(ControllerBase):
    @http_get("/{int:client_id}/bookings", response=List[BookingOut])
    def client_bookings(self, client_id: int):
        try:
            client = ClientProfile.objects.get(id=client_id)
        except ClientProfile.DoesNotExist:
            raise HttpError(404, "Client not found.")
        user = self.context.request.user
        if not is_admin(user):
            own_id = getattr(getattr(user, "client_profile", None), "id", None)
            if own_id != client.id:
                raise HttpError(403, "You do not have permission to view this booking.")
        return list(get_client_bookings(client))
