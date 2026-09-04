from datetime import date
from decimal import Decimal

from django.test import TestCase

from bookings.models import Booking, BookingStatus
from bookings.services import check_property_availability, create_booking
from bookings.tests.helpers import make_client, make_property, make_provider


class PropertyAvailabilityTest(TestCase):
    def setUp(self):
        self.provider = make_provider()
        self.property = make_property(self.provider)
        self.client = make_client()

    def test_available_when_empty(self):
        self.assertTrue(
            check_property_availability(
                self.property, date(2026, 10, 1), date(2026, 12, 1)
            )
        )

    def test_overlapping_booking_not_available(self):
        Booking.objects.create(
            client=self.client,
            provider=self.provider,
            property_ref=self.property,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 12, 1),
            monthly_price=Decimal("5000.00"),
            number_of_months=2,
            total_price=Decimal("10000.00"),
            status=BookingStatus.APPROVED,
        )
        self.assertFalse(
            check_property_availability(
                self.property, date(2026, 11, 1), date(2027, 1, 1)
            )
        )

    def test_adjacent_bookings_allowed(self):
        Booking.objects.create(
            client=self.client,
            provider=self.provider,
            property_ref=self.property,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 11, 1),
            monthly_price=Decimal("5000.00"),
            number_of_months=1,
            total_price=Decimal("5000.00"),
            status=BookingStatus.ACTIVE,
        )
        self.assertTrue(
            check_property_availability(
                self.property, date(2026, 11, 1), date(2026, 12, 1)
            )
        )
        create_booking(
            client=self.client,
            property_obj=self.property,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 1),
        )

    def test_cancelled_and_rejected_ignored(self):
        for status in (BookingStatus.CANCELLED, BookingStatus.REJECTED, BookingStatus.EXPIRED):
            Booking.objects.create(
                client=self.client,
                provider=self.provider,
                property_ref=self.property,
                start_date=date(2026, 10, 1),
                end_date=date(2026, 11, 1),
                monthly_price=Decimal("5000.00"),
                number_of_months=1,
                total_price=Decimal("5000.00"),
                status=status,
            )
        self.assertTrue(
            check_property_availability(
                self.property, date(2026, 10, 1), date(2026, 11, 1)
            )
        )
