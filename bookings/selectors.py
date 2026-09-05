"""Read-side queries for bookings, dashboard, and reports."""
from datetime import date
from decimal import Decimal
from typing import Optional

from django.db.models import Q, QuerySet, Sum
from django.utils import timezone

from bookings.models import Booking, BookingPayment, BookingStatus, PaymentStatus
from users.models import ClientProfile, Property, ProviderProfile, UserRole
from users.permissions import get_user_role, is_admin


def get_bookings(
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    client: Optional[ClientProfile] = None,
    property_obj: Optional[Property] = None,
    provider: Optional[ProviderProfile] = None,
    search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> QuerySet:
    queryset = Booking.objects.select_related(
        "client__user",
        "provider__user",
        "property_ref",
    ).all()

    if status:
        queryset = queryset.filter(status=status)
    if payment_status:
        queryset = queryset.filter(payment_status=payment_status)
    if client:
        queryset = queryset.filter(client=client)
    if property_obj:
        queryset = queryset.filter(property_ref=property_obj)
    if provider:
        queryset = queryset.filter(provider=provider)
    if start_date:
        queryset = queryset.filter(start_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(end_date__lte=end_date)
    if search:
        queryset = search_bookings(search, queryset)

    return queryset.order_by("-created_at")


def apply_user_scope(queryset: QuerySet, user) -> QuerySet:
    if is_admin(user):
        return queryset
    role = get_user_role(user)
    if role == UserRole.PROVIDER:
        return queryset.filter(provider=user.provider_profile)
    if role == UserRole.CLIENT:
        return queryset.filter(client=user.client_profile)
    return queryset.none()


def get_booking_by_id(booking_id: int) -> Optional[Booking]:
    try:
        return Booking.objects.select_related(
            "client__user",
            "provider__user",
            "property_ref",
        ).get(id=booking_id)
    except Booking.DoesNotExist:
        return None


def get_client_bookings(client: ClientProfile) -> QuerySet:
    return (
        Booking.objects.filter(client=client)
        .select_related("provider__user", "property_ref")
        .order_by("-created_at")
    )


def get_property_bookings(property_obj: Property) -> QuerySet:
    return (
        Booking.objects.filter(property_ref=property_obj)
        .select_related("client__user", "provider__user")
        .order_by("start_date")
    )


def get_booking_payments(booking: Booking) -> QuerySet:
    return BookingPayment.objects.filter(booking=booking).select_related(
        "received_by"
    ).order_by("-received_at")


def get_pending_bookings() -> QuerySet:
    return Booking.objects.filter(status=BookingStatus.PENDING).select_related(
        "client__user", "provider__user", "property_ref"
    )


def get_active_bookings() -> QuerySet:
    return Booking.objects.filter(status=BookingStatus.ACTIVE).select_related(
        "client__user", "property_ref"
    )


def get_occupied_properties(today: Optional[date] = None) -> int:
    today = today or date.today()
    return (
        Booking.objects.filter(
            status=BookingStatus.ACTIVE,
            start_date__lte=today,
            end_date__gt=today,
        )
        .values("property_ref")
        .distinct()
        .count()
    )


def get_available_properties(today: Optional[date] = None) -> int:
    total_properties = Property.objects.filter(is_active=True).count()
    return total_properties - get_occupied_properties(today)


def get_total_payments_today() -> Decimal:
    today = timezone.localdate()
    result = BookingPayment.objects.filter(
        received_at__date=today,
        status=PaymentStatus.PAID,
    ).aggregate(total=Sum("amount"))
    return result["total"] or Decimal("0.00")


def get_total_payments_this_month() -> Decimal:
    today = timezone.localdate()
    month_start = today.replace(day=1)
    result = BookingPayment.objects.filter(
        received_at__date__gte=month_start,
        status=PaymentStatus.PAID,
    ).aggregate(total=Sum("amount"))
    return result["total"] or Decimal("0.00")


def get_outstanding_balance() -> Decimal:
    outstanding = Decimal("0.00")
    for booking in Booking.objects.filter(
        payment_status__in=[PaymentStatus.UNPAID, PaymentStatus.PARTIAL]
    ):
        outstanding += booking.remaining_balance
    return outstanding


def get_monthly_revenue(year: int, month: int) -> Decimal:
    result = BookingPayment.objects.filter(
        received_at__year=year,
        received_at__month=month,
        status=PaymentStatus.PAID,
    ).aggregate(total=Sum("amount"))
    return result["total"] or Decimal("0.00")


def get_outstanding_payments() -> QuerySet:
    return Booking.objects.filter(
        payment_status__in=[PaymentStatus.UNPAID, PaymentStatus.PARTIAL]
    ).select_related("client__user", "property_ref").order_by("-created_at")


def search_bookings(query: str, queryset: Optional[QuerySet] = None) -> QuerySet:
    queryset = queryset if queryset is not None else Booking.objects.all()
    lookup = (
        Q(client__user__first_name__icontains=query)
        | Q(client__user__last_name__icontains=query)
        | Q(client__phone__icontains=query)
        | Q(property_ref__name__icontains=query)
        | Q(provider__user__first_name__icontains=query)
        | Q(provider__user__last_name__icontains=query)
        | Q(provider__company_name__icontains=query)
    )
    if query.isdigit():
        lookup = lookup | Q(id=int(query))
    return queryset.filter(lookup).select_related(
        "client__user", "provider__user", "property_ref"
    )


def get_dashboard() -> dict:
    today = date.today()
    return {
        "today": today,
        "total_properties": Property.objects.filter(is_active=True).count(),
        "available_properties": get_available_properties(today),
        "occupied_properties": get_occupied_properties(today),
        "active_bookings": get_active_bookings().count(),
        "pending_bookings": get_pending_bookings().count(),
        "completed_bookings": Booking.objects.filter(
            status=BookingStatus.COMPLETED
        ).count(),
        "today_payments": get_total_payments_today(),
        "month_payments": get_total_payments_this_month(),
        "outstanding_balance": get_outstanding_balance(),
    }


def get_property_availability_calendar(
    property_obj: Property,
    start_date: date,
    end_date: date,
) -> list[dict]:
    bookings = (
        Booking.objects.filter(
            property_ref=property_obj,
            start_date__lt=end_date,
            end_date__gt=start_date,
        )
        .exclude(
            status__in=[
                BookingStatus.REJECTED,
                BookingStatus.CANCELLED,
                BookingStatus.EXPIRED,
            ]
        )
        .order_by("start_date")
    )

    intervals = []
    cursor = start_date
    for booking in bookings:
        booked_start = max(booking.start_date, start_date)
        booked_end = min(booking.end_date, end_date)
        if cursor < booked_start:
            intervals.append(
                {
                    "start_date": cursor,
                    "end_date": booked_start,
                    "status": "available",
                    "booking_id": None,
                }
            )
        status = "pending" if booking.status == BookingStatus.PENDING else "booked"
        intervals.append(
            {
                "start_date": booked_start,
                "end_date": booked_end,
                "status": status,
                "booking_id": booking.id,
            }
        )
        if booked_end > cursor:
            cursor = booked_end
    if cursor < end_date:
        intervals.append(
            {
                "start_date": cursor,
                "end_date": end_date,
                "status": "available",
                "booking_id": None,
            }
        )
    return intervals
