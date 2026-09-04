import json
from datetime import date

from django.test import TestCase

from bookings.models import BookingStatus, PaymentStatus
from bookings.services import create_booking
from bookings.tests.helpers import make_admin, make_client, make_property, make_provider


class BookingApiFlowTest(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.provider = make_provider()
        self.client_profile = make_client()
        self.property = make_property(self.provider)
        self.client.force_login(self.admin)

    def test_create_list_filter_search_pay_and_reports(self):
        created = self.client.post(
            "/api/bookings",
            data=json.dumps(
                {
                    "client_id": self.client_profile.id,
                    "property_id": self.property.id,
                    "provider_id": self.provider.id,
                    "property_ref_id": self.property.id,
                    "start_date": "2026-10-01",
                    "end_date": "2026-12-01",
                    "notes": "Monthly rental",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 200, created.content)
        body = created.json()
        self.assertEqual(body["status"], BookingStatus.PENDING)
        self.assertEqual(body["payment_status"], PaymentStatus.UNPAID)
        self.assertEqual(body["payment_method"], "cash")
        self.assertEqual(body["number_of_months"], 2)
        self.assertEqual(body["total_price"], "10000.00")
        booking_id = body["id"]

        listed = self.client.get("/api/bookings?search=Ahmed&status=pending")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)

        unpaid = self.client.get("/api/bookings?payment_status=unpaid")
        self.assertEqual(len(unpaid.json()), 1)

        availability = self.client.get(
            f"/api/properties/{self.property.id}/availability"
            "?start_date=2026-10-01&end_date=2026-12-01"
        )
        self.assertEqual(availability.status_code, 200)
        self.assertFalse(availability.json()["available"])
        statuses = {item["status"] for item in availability.json()["intervals"]}
        self.assertIn("pending", statuses)

        approve = self.client.post(
            f"/api/bookings/{booking_id}/approve",
            data=json.dumps({"notes": ""}),
            content_type="application/json",
        )
        self.assertEqual(approve.status_code, 200)
        self.assertEqual(approve.json()["status"], BookingStatus.APPROVED)

        payment = self.client.post(
            f"/api/bookings/{booking_id}/payments",
            data=json.dumps(
                {
                    "amount": "5000.00",
                    "payment_method": "cash",
                    "received_by_user": "Admin",
                    "notes": "First cash installment",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(payment.status_code, 200, payment.content)
        payment_id = payment.json()["id"]

        history = self.client.get(f"/api/bookings/{booking_id}/payments")
        self.assertEqual(len(history.json()), 1)

        receipt = self.client.get(
            f"/api/bookings/{booking_id}/payments/{payment_id}/receipt"
        )
        self.assertEqual(receipt.status_code, 200)
        self.assertEqual(receipt["Content-Type"], "application/pdf")

        html = self.client.get(
            f"/api/bookings/{booking_id}/payments/{payment_id}/receipt.html"
        )
        self.assertEqual(html.status_code, 200)
        self.assertIn(b"HOMEZUP", html.content)

        dashboard = self.client.get("/api/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["pending_bookings"], 0)

        revenue = self.client.get("/api/reports/revenue?year=2026&month=9")
        self.assertEqual(revenue.status_code, 200)

        outstanding = self.client.get("/api/reports/outstanding")
        self.assertEqual(outstanding.status_code, 200)
        self.assertEqual(outstanding.json()[0]["remaining_balance"], "5000.00")

        occupancy = self.client.get("/api/reports/occupancy")
        self.assertEqual(occupancy.status_code, 200)

        exports = self.client.get("/api/exports/bookings.csv")
        self.assertEqual(exports.status_code, 200)
        self.assertIn(b"booking_id", exports.content)

        client_bookings = self.client.get(
            f"/api/clients/{self.client_profile.id}/bookings"
        )
        self.assertEqual(client_bookings.status_code, 200)
        self.assertEqual(len(client_bookings.json()), 1)

    def test_invalid_dates_return_api_error(self):
        response = self.client.post(
            "/api/bookings",
            data=json.dumps(
                {
                    "client_id": self.client_profile.id,
                    "property_id": self.property.id,
                    "start_date": "2026-12-01",
                    "end_date": "2026-10-01",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("date", response.json()["detail"].lower())

    def test_login(self):
        self.client.logout()
        response = self.client.post(
            "/api/auth/login",
            data=json.dumps({"username": "admin", "password": "admin123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["role"], "admin")
