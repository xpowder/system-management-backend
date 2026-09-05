import json
from datetime import date
from decimal import Decimal
from unittest import skip

from django.test import TestCase

from bookings.models import Booking, BookingStatus
from bookings.services import create_booking
from bookings.tests.helpers import (
    make_admin,
    make_client,
    make_property,
    make_provider,
)


@skip("Booking HTTP APIs are paused")
class BookingPermissionApiTest(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.provider = make_provider()
        self.other_provider = make_provider(username="provider2", first_name="Karim")
        self.client_profile = make_client()
        self.other_client = make_client(username="client2", first_name="Youssef", phone="0699999999")
        self.property = make_property(self.provider)
        self.other_property = make_property(self.other_provider, name="Villa B")
        self.booking = create_booking(
            client=self.client_profile,
            property_obj=self.property,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 12, 1),
        )

    def _login(self, user):
        self.client.force_login(user)

    def test_unauthorized_user(self):
        response = self.client.get("/api/bookings")
        self.assertEqual(response.status_code, 401)

    def test_admin_full_access(self):
        self._login(self.admin)
        response = self.client.get("/api/bookings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

        created = self.client.post(
            "/api/bookings",
            data=json.dumps(
                {
                    "client_id": self.other_client.id,
                    "property_id": self.other_property.id,
                    "start_date": "2026-10-01",
                    "end_date": "2026-11-01",
                    "notes": "Monthly rental",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 200, created.content)

    def test_provider_sees_own_bookings_only(self):
        create_booking(
            client=self.other_client,
            property_obj=self.other_property,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 11, 1),
        )
        self._login(self.provider.user)
        response = self.client.get("/api/bookings")
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()]
        self.assertEqual(ids, [self.booking.id])

    def test_client_sees_own_bookings_only(self):
        create_booking(
            client=self.other_client,
            property_obj=self.other_property,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 11, 1),
        )
        self._login(self.client_profile.user)
        response = self.client.get("/api/bookings")
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()]
        self.assertEqual(ids, [self.booking.id])

    def test_client_cannot_create_booking(self):
        self._login(self.client_profile.user)
        response = self.client.post(
            "/api/bookings",
            data=json.dumps(
                {
                    "client_id": self.client_profile.id,
                    "property_id": self.property.id,
                    "start_date": "2027-01-01",
                    "end_date": "2027-02-01",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_provider_cannot_modify_foreign_booking(self):
        foreign = create_booking(
            client=self.other_client,
            property_obj=self.other_property,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 11, 1),
        )
        self._login(self.provider.user)
        response = self.client.post(
            f"/api/bookings/{foreign.id}/approve",
            data=json.dumps({"notes": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_named_admin_group_sees_all_bookings(self):
        from django.contrib.auth.models import Group, User

        staff = User.objects.create_user(
            username="group-admin",
            password="password123",
            is_staff=True,
        )
        Group.objects.get_or_create(name="Admin")[0].user_set.add(staff)
        self._login(staff)
        response = self.client.get("/api/bookings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_provider_cannot_read_another_providers_availability(self):
        self._login(self.provider.user)
        own = self.client.get(f"/api/properties/{self.property.id}/availability")
        other = self.client.get(f"/api/properties/{self.other_property.id}/availability")
        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 403)
