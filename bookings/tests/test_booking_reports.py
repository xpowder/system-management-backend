from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from bookings.models import Booking, BookingPayment, BookingStatus, PaymentStatus
from bookings.selectors import get_dashboard, get_monthly_revenue, get_outstanding_payments
from bookings.tests.helpers import make_client, make_property, make_provider


class BookingReportTest(TestCase):
    def setUp(self):
        self.provider = make_provider()
        self.client = make_client()
        self.property = make_property(self.provider)
        today = date.today()
        self.booking = Booking.objects.create(
            client=self.client,
            provider=self.provider,
            property_ref=self.property,
            start_date=today,
            end_date=today.replace(year=today.year + 1) if today.month == 1 else today.replace(month=today.month + 1) if today.month < 12 else date(today.year + 1, 1, today.day if today.day <= 28 else 28),
            monthly_price=Decimal("5000.00"),
            number_of_months=2,
            total_price=Decimal("10000.00"),
            status=BookingStatus.ACTIVE,
            payment_status=PaymentStatus.PARTIAL,
        )
        BookingPayment.objects.create(
            booking=self.booking,
            amount=Decimal("4000.00"),
            received_by_user="Admin",
            receipt_number="HZ-REV-1",
        )

    def test_revenue(self):
        now = timezone.now()
        total = get_monthly_revenue(now.year, now.month)
        self.assertEqual(total, Decimal("4000.00"))

    def test_outstanding(self):
        rows = list(get_outstanding_payments())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].remaining_balance, Decimal("6000.00"))

    def test_occupancy_and_dashboard(self):
        data = get_dashboard()
        self.assertEqual(data["total_properties"], 1)
        self.assertEqual(data["occupied_properties"], 1)
        self.assertEqual(data["available_properties"], 0)
        self.assertEqual(data["outstanding_balance"], Decimal("6000.00"))
        self.assertEqual(data["today_payments"], Decimal("4000.00"))
