"""Local CSV exports for the receptionist workflow."""
import csv
from io import StringIO

from django.http import HttpResponse

from bookings.models import Booking, BookingPayment, PaymentStatus
from bookings.selectors import get_monthly_revenue, get_outstanding_payments


def _csv_response(filename: str, header: list, rows) -> HttpResponse:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_bookings_csv(queryset=None) -> HttpResponse:
    queryset = queryset if queryset is not None else Booking.objects.select_related(
        "client__user", "provider__user", "property_ref"
    )
    rows = [
        [
            booking.id,
            f"{booking.client.user.first_name} {booking.client.user.last_name}",
            booking.property_ref.name,
            booking.provider.user.username,
            booking.start_date,
            booking.end_date,
            booking.monthly_price,
            booking.number_of_months,
            booking.total_price,
            booking.status,
            booking.payment_status,
            booking.remaining_balance,
        ]
        for booking in queryset
    ]
    return _csv_response(
        "AUMB-bookings.csv",
        [
            "booking_id",
            "client",
            "property",
            "provider",
            "start_date",
            "end_date",
            "monthly_price",
            "months",
            "total_price",
            "status",
            "payment_status",
            "remaining_balance",
        ],
        rows,
    )


def export_payments_csv() -> HttpResponse:
    rows = [
        [
            payment.id,
            payment.booking_id,
            payment.amount,
            payment.payment_method,
            payment.received_by_user,
            payment.received_at,
            payment.receipt_number,
        ]
        for payment in BookingPayment.objects.select_related("booking")
    ]
    return _csv_response(
        "AUMB-payments.csv",
        [
            "payment_id",
            "booking_id",
            "amount",
            "payment_method",
            "received_by",
            "received_at",
            "receipt_number",
        ],
        rows,
    )


def export_outstanding_csv() -> HttpResponse:
    rows = [
        [
            booking.id,
            f"{booking.client.user.first_name} {booking.client.user.last_name}",
            booking.property_ref.name,
            booking.total_price,
            booking.total_paid,
            booking.remaining_balance,
            booking.payment_status,
        ]
        for booking in get_outstanding_payments()
    ]
    return _csv_response(
        "AUMB-outstanding.csv",
        [
            "booking_id",
            "client",
            "property",
            "total_price",
            "total_paid",
            "remaining_balance",
            "payment_status",
        ],
        rows,
    )


def export_revenue_csv(year: int, month: int) -> HttpResponse:
    cash = get_monthly_revenue(year, month)
    return _csv_response(
        f"AUMB-revenue-{year}-{month:02d}.csv",
        ["year", "month", "cash_collected", "currency"],
        [[year, month, cash, "MAD"]],
    )
