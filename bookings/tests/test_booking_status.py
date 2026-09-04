from datetime import date
from decimal import Decimal

from django.test import TestCase

from bookings.exceptions import BookingCannotBeCancelled, InvalidStatusTransition
from bookings.models import Booking, BookingStatus
from bookings.services import (
    approve_booking,
    cancel_booking,
    reject_booking,
    update_booking_statuses,
)
from bookings.tests.helpers import make_client, make_property, make_provider


class BookingStatusTransitionTest(TestCase):
    def setUp(self):
        self.provider = make_provider()
        self.client = make_client()
        self.property = make_property(self.provider)
        self.booking = Booking.objects.create(
            client=self.client,
            provider=self.provider,
            property_ref=self.property,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 12, 1),
            monthly_price=Decimal("5000.00"),
            number_of_months=2,
            total_price=Decimal("10000.00"),
        )

    def test_approve_pending(self):
        booking = approve_booking(self.booking)
        self.assertEqual(booking.status, BookingStatus.APPROVED)
        self.assertIsNotNone(booking.approved_at)

    def test_cannot_approve_active(self):
        self.booking.status = BookingStatus.ACTIVE
        self.booking.save()
        with self.assertRaises(InvalidStatusTransition):
            approve_booking(self.booking)

    def test_reject_pending(self):
        booking = reject_booking(self.booking)
        self.assertEqual(booking.status, BookingStatus.REJECTED)

    def test_cannot_reject_approved(self):
        approve_booking(self.booking)
        with self.assertRaises(InvalidStatusTransition):
            reject_booking(self.booking)

    def test_cancel_approved(self):
        approve_booking(self.booking)
        booking = cancel_booking(self.booking)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.assertIsNotNone(booking.cancelled_at)

    def test_cannot_cancel_completed(self):
        self.booking.status = BookingStatus.COMPLETED
        self.booking.save()
        with self.assertRaises(BookingCannotBeCancelled):
            cancel_booking(self.booking)

    def test_update_approved_to_active(self):
        approve_booking(self.booking)
        update_booking_statuses(today=date(2026, 10, 1))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.ACTIVE)

    def test_update_active_to_completed(self):
        self.booking.status = BookingStatus.ACTIVE
        self.booking.save()
        update_booking_statuses(today=date(2026, 12, 1))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.COMPLETED)
        self.assertIsNotNone(self.booking.completed_at)

    def test_update_is_idempotent(self):
        approve_booking(self.booking)
        update_booking_statuses(today=date(2026, 10, 1))
        update_booking_statuses(today=date(2026, 10, 1))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.ACTIVE)
