"""Booking business logic. Controllers must not calculate prices or availability."""
from datetime import date
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from bookings.exceptions import (
    BookingCannotBeCancelled,
    DuplicatePayment,
    InvalidBookingDates,
    InvalidClient,
    InvalidPaymentAmount,
    InvalidProperty,
    InvalidStatusTransition,
    PaymentExceedsBalance,
    PropertyUnavailable,
)
from bookings.models import (
    Booking,
    BookingPayment,
    BookingStatus,
    PaymentMethod,
    PaymentStatus,
)
from users.models import ClientProfile, Property


INACTIVE_AVAILABILITY_STATUSES = (
    BookingStatus.REJECTED,
    BookingStatus.CANCELLED,
    BookingStatus.EXPIRED,
)


def calculate_booking_months(start_date: date, end_date: date) -> int:
    """Calendar-month duration for [start_date, end_date)."""
    if end_date <= start_date:
        raise InvalidBookingDates("Invalid booking dates.")

    delta = relativedelta(end_date, start_date)
    months = delta.years * 12 + delta.months
    if delta.days > 0 or delta.hours or delta.minutes or delta.seconds:
        months += 1
    if months < 1:
        raise InvalidBookingDates("Invalid booking dates.")
    return months


def calculate_booking_price(monthly_price: Decimal, number_of_months: int) -> Decimal:
    if number_of_months < 1:
        raise InvalidBookingDates("Number of months must be at least 1.")
    price = Decimal(str(monthly_price)) * Decimal(number_of_months)
    return price.quantize(Decimal("0.01"))


def calculate_remaining_balance(booking: Booking) -> Decimal:
    return booking.remaining_balance


def check_property_availability(
    property_obj: Property,
    start_date: date,
    end_date: date,
    exclude_booking_id: Optional[int] = None,
) -> bool:
    if end_date <= start_date:
        raise InvalidBookingDates("Invalid booking dates.")

    bookings = Booking.objects.filter(property_ref=property_obj).exclude(
        status__in=INACTIVE_AVAILABILITY_STATUSES
    )
    if exclude_booking_id:
        bookings = bookings.exclude(id=exclude_booking_id)

    overlap = Q(start_date__lt=end_date) & Q(end_date__gt=start_date)
    return not bookings.filter(overlap).exists()


def create_booking(
    client: ClientProfile,
    property_obj: Property,
    start_date: date,
    end_date: date,
    notes: str = "",
    provider=None,
) -> Booking:
    """
    Create a pending unpaid cash booking.

    Provider and prices are taken from the property. `provider` is ignored
    unless it does not match the property owner, in which case it is rejected.
    """
    if client is None or getattr(client, "pk", None) is None:
        raise InvalidClient("Invalid client.")
    if property_obj is None or getattr(property_obj, "pk", None) is None:
        raise InvalidProperty("Invalid property.")
    if not property_obj.is_active:
        raise InvalidProperty("Invalid property.")
    if provider is not None and provider.pk != property_obj.provider_id:
        raise InvalidProperty("Provider does not match the selected property.")

    with transaction.atomic():
        locked_property = Property.objects.select_for_update().get(pk=property_obj.pk)
        if not check_property_availability(locked_property, start_date, end_date):
            raise PropertyUnavailable("Property is already booked for these dates.")

        number_of_months = calculate_booking_months(start_date, end_date)
        monthly_price = locked_property.monthly_price
        total_price = calculate_booking_price(monthly_price, number_of_months)

        return Booking.objects.create(
            client=client,
            provider=locked_property.provider,
            property_ref=locked_property,
            start_date=start_date,
            end_date=end_date,
            monthly_price=monthly_price,
            number_of_months=number_of_months,
            total_price=total_price,
            status=BookingStatus.PENDING,
            payment_status=PaymentStatus.UNPAID,
            payment_method=PaymentMethod.CASH,
            notes=notes or "",
        )


@transaction.atomic
def approve_booking(booking: Booking, notes: str = "") -> Booking:
    if booking.status != BookingStatus.PENDING:
        raise InvalidStatusTransition(
            f"Can only approve pending bookings. Current status is {booking.status}."
        )
    booking.status = BookingStatus.APPROVED
    booking.approved_at = timezone.now()
    if notes:
        booking.notes = notes
    booking.save(update_fields=["status", "approved_at", "notes", "updated_at"])
    return booking


@transaction.atomic
def reject_booking(booking: Booking, notes: str = "") -> Booking:
    if booking.status != BookingStatus.PENDING:
        raise InvalidStatusTransition(
            f"Can only reject pending bookings. Current status is {booking.status}."
        )
    booking.status = BookingStatus.REJECTED
    if notes:
        booking.notes = notes
    booking.save(update_fields=["status", "notes", "updated_at"])
    return booking


@transaction.atomic
def cancel_booking(booking: Booking, notes: str = "") -> Booking:
    if booking.status == BookingStatus.COMPLETED:
        raise BookingCannotBeCancelled(
            "Booking cannot be cancelled because it has already been completed."
        )
    if booking.status in (
        BookingStatus.CANCELLED,
        BookingStatus.REJECTED,
        BookingStatus.EXPIRED,
    ):
        raise InvalidStatusTransition(f"Booking is already {booking.status}.")
    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = timezone.now()
    if notes:
        booking.notes = notes
    booking.save(update_fields=["status", "cancelled_at", "notes", "updated_at"])
    return booking


def record_cash_payment(
    booking: Booking,
    amount: Decimal,
    received_by_user: str = "",
    receipt_number: str = "",
    notes: str = "",
    received_by=None,
) -> BookingPayment:
    amount = Decimal(str(amount))
    if amount <= 0:
        raise InvalidPaymentAmount("Payment amount must be greater than 0.")

    with transaction.atomic():
        locked = Booking.objects.select_for_update().get(pk=booking.pk)
        remaining = calculate_remaining_balance(locked)
        if amount > remaining:
            raise PaymentExceedsBalance(
                f"Payment amount exceeds remaining balance of {remaining} MAD."
            )

        display_name = received_by_user
        if not display_name and received_by is not None:
            display_name = (
                received_by.get_full_name().strip() or received_by.username
            )
        if not display_name:
            display_name = "Admin"

        try:
            payment = BookingPayment(
                booking=locked,
                amount=amount,
                payment_method=PaymentMethod.CASH,
                status=PaymentStatus.PAID,
                received_by=received_by,
                received_by_user=display_name,
                notes=notes or "",
            )
            if receipt_number:
                payment.receipt_number = receipt_number
            payment.save()
        except IntegrityError as exc:
            raise DuplicatePayment(
                "A payment with this receipt number already exists."
            ) from exc

        return payment


def update_booking_statuses(today: Optional[date] = None) -> dict:
    """Idempotent status progression. Safe to run repeatedly."""
    today = today or date.today()

    activated = Booking.objects.filter(
        status=BookingStatus.APPROVED,
        start_date__lte=today,
    ).update(status=BookingStatus.ACTIVE)

    completed = Booking.objects.filter(
        status=BookingStatus.ACTIVE,
        end_date__lte=today,
    ).update(status=BookingStatus.COMPLETED, completed_at=timezone.now())

    return {"activated": activated, "completed": completed}
