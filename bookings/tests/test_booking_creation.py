from datetime import date
from decimal import Decimal

from django.test import TestCase

from bookings.exceptions import InvalidBookingDates, InvalidProperty, PropertyUnavailable
from bookings.models import Booking, BookingStatus, PaymentMethod, PaymentStatus
from bookings.services import calculate_booking_months, calculate_booking_price, create_booking
from bookings.tests.helpers import make_client, make_property, make_provider


class BookingMonthCalculationTest(TestCase):
    def test_one_month(self):
        self.assertEqual(
            calculate_booking_months(date(2026, 10, 1), date(2026, 11, 1)), 1
        )

    def test_two_months(self):
        self.assertEqual(
            calculate_booking_months(date(2026, 10, 1), date(2026, 12, 1)), 2
        )

    def test_three_months(self):
        self.assertEqual(
            calculate_booking_months(date(2026, 10, 1), date(2027, 1, 1)), 3
        )

    def test_year_transition(self):
        self.assertEqual(
            calculate_booking_months(date(2026, 12, 1), date(2027, 1, 1)), 1
        )

    def test_january_to_february(self):
        self.assertEqual(
            calculate_booking_months(date(2026, 1, 1), date(2026, 2, 1)), 1
        )

    def test_february_to_march(self):
        self.assertEqual(
            calculate_booking_months(date(2026, 2, 1), date(2026, 3, 1)), 1
        )

    def test_leap_year_february(self):
        self.assertEqual(
            calculate_booking_months(date(2024, 2, 1), date(2024, 3, 1)), 1
        )
        self.assertEqual(
            calculate_booking_months(date(2024, 1, 31), date(2024, 2, 29)), 1
        )

    def test_invalid_dates(self):
        with self.assertRaises(InvalidBookingDates):
            calculate_booking_months(date(2026, 12, 1), date(2026, 11, 1))
        with self.assertRaises(InvalidBookingDates):
            calculate_booking_months(date(2026, 10, 1), date(2026, 10, 1))


class BookingPriceCalculationTest(TestCase):
    def test_prices(self):
        self.assertEqual(calculate_booking_price(Decimal("5000.00"), 1), Decimal("5000.00"))
        self.assertEqual(calculate_booking_price(Decimal("5000.00"), 2), Decimal("10000.00"))
        self.assertEqual(calculate_booking_price(Decimal("5000.00"), 3), Decimal("15000.00"))
        self.assertEqual(calculate_booking_price(Decimal("5500.50"), 2), Decimal("11001.00"))


class BookingCreationTest(TestCase):
    def setUp(self):
        self.provider = make_provider()
        self.client = make_client()
        self.property = make_property(self.provider)

    def test_create_valid_booking(self):
        booking = create_booking(
            client=self.client,
            property_obj=self.property,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 12, 1),
            notes="Monthly rental",
        )
        self.assertEqual(booking.status, BookingStatus.PENDING)
        self.assertEqual(booking.payment_status, PaymentStatus.UNPAID)
        self.assertEqual(booking.payment_method, PaymentMethod.CASH)
        self.assertEqual(booking.provider, self.provider)
        self.assertEqual(booking.number_of_months, 2)
        self.assertEqual(booking.total_price, Decimal("10000.00"))
        self.assertEqual(booking.monthly_price, Decimal("5000.00"))

    def test_price_snapshot_is_frozen(self):
        booking = create_booking(
            client=self.client,
            property_obj=self.property,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 11, 1),
        )
        self.property.monthly_price = Decimal("6000.00")
        self.property.save()
        booking.refresh_from_db()
        self.assertEqual(booking.monthly_price, Decimal("5000.00"))
        self.assertEqual(booking.total_price, Decimal("5000.00"))

    def test_provider_is_taken_from_property(self):
        booking = create_booking(
            client=self.client,
            provider=self.provider,
            property_obj=self.property,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 11, 1),
        )
        self.assertEqual(booking.provider_id, self.property.provider_id)

    def test_invalid_dates(self):
        with self.assertRaises(InvalidBookingDates):
            create_booking(
                client=self.client,
                property_obj=self.property,
                start_date=date(2026, 12, 1),
                end_date=date(2026, 10, 1),
            )

    def test_inactive_property(self):
        self.property.is_active = False
        self.property.save()
        with self.assertRaises(InvalidProperty):
            create_booking(
                client=self.client,
                property_obj=self.property,
                start_date=date(2026, 10, 1),
                end_date=date(2026, 11, 1),
            )

    def test_overlapping_rejected(self):
        create_booking(
            client=self.client,
            property_obj=self.property,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 11, 1),
        )
        with self.assertRaises(PropertyUnavailable):
            create_booking(
                client=self.client,
                property_obj=self.property,
                start_date=date(2026, 10, 15),
                end_date=date(2026, 11, 15),
            )
