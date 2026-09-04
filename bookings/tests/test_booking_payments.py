from datetime import date
from decimal import Decimal

from django.test import TestCase

from bookings.exceptions import DuplicatePayment, InvalidPaymentAmount, PaymentExceedsBalance
from bookings.models import Booking, PaymentStatus
from bookings.services import calculate_remaining_balance, record_cash_payment
from bookings.tests.helpers import make_admin, make_client, make_property, make_provider


class PaymentTest(TestCase):
    def setUp(self):
        self.provider = make_provider()
        self.client = make_client()
        self.property = make_property(self.provider)
        self.admin = make_admin()
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

    def test_cash_payment_full(self):
        payment = record_cash_payment(
            booking=self.booking,
            amount=Decimal("10000.00"),
            received_by_user="Admin",
            received_by=self.admin,
        )
        self.booking.refresh_from_db()
        self.assertEqual(payment.payment_method, "cash")
        self.assertEqual(self.booking.payment_status, PaymentStatus.PAID)
        self.assertEqual(calculate_remaining_balance(self.booking), Decimal("0.00"))

    def test_partial_then_full(self):
        record_cash_payment(self.booking, Decimal("5000.00"), received_by_user="Admin")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, PaymentStatus.PARTIAL)
        self.assertEqual(self.booking.remaining_balance, Decimal("5000.00"))

        record_cash_payment(self.booking, Decimal("5000.00"), received_by_user="Admin")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, PaymentStatus.PAID)
        self.assertEqual(self.booking.remaining_balance, Decimal("0.00"))
        self.assertEqual(self.booking.payments.count(), 2)

    def test_payment_exceeds_remaining(self):
        with self.assertRaises(PaymentExceedsBalance):
            record_cash_payment(self.booking, Decimal("15000.00"), received_by_user="Admin")

    def test_invalid_amount(self):
        with self.assertRaises(InvalidPaymentAmount):
            record_cash_payment(self.booking, Decimal("-1000.00"), received_by_user="Admin")
        with self.assertRaises(InvalidPaymentAmount):
            record_cash_payment(self.booking, Decimal("0"), received_by_user="Admin")

    def test_duplicate_receipt_number(self):
        record_cash_payment(
            self.booking,
            Decimal("1000.00"),
            received_by_user="Admin",
            receipt_number="HZ-DUP-1",
        )
        with self.assertRaises(DuplicatePayment):
            record_cash_payment(
                self.booking,
                Decimal("1000.00"),
                received_by_user="Admin",
                receipt_number="HZ-DUP-1",
            )

    def test_payment_history_and_remaining(self):
        record_cash_payment(self.booking, Decimal("3000.00"), received_by_user="Admin")
        record_cash_payment(self.booking, Decimal("2000.00"), received_by_user="Admin")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.total_paid, Decimal("5000.00"))
        self.assertEqual(self.booking.remaining_balance, Decimal("5000.00"))
        self.assertEqual(list(self.booking.payments.values_list("amount", flat=True)).__len__(), 2)
