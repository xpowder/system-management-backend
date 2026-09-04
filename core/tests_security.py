import json

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase

from bookings.tests.helpers import make_admin, make_client, make_provider
from fitness.models import GymNotification
from users.models import ClientProfile


class UnauthenticatedAccessTests(TestCase):
    def test_private_gym_and_account_endpoints_require_login(self):
        paths = [
            ('get', '/api/auth/me'),
            ('get', '/api/fitness/members'),
            ('get', '/api/fitness/payments'),
            ('get', '/api/notifications'),
            ('get', '/api/admin/users'),
            ('get', '/api/clients'),
            ('get', '/api/bookings'),
            ('post', '/api/fitness/members'),
        ]
        for method, path in paths:
            response = getattr(self.client, method)(path, content_type='application/json')
            self.assertEqual(response.status_code, 401, path)

    def test_invalid_bearer_token_does_not_authenticate(self):
        response = self.client.get(
            '/api/fitness/members',
            HTTP_AUTHORIZATION='Bearer invalid-token',
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(b'Traceback', response.content)


class GymStaffAuthorizationTests(TestCase):
    def setUp(self):
        self.member_user = User.objects.create_user(
            username='gym-member',
            password='password123',
            first_name='Member',
        )
        self.member = ClientProfile.objects.create(user=self.member_user, id_number='SEC-MEM')
        self.provider = make_provider(username='sec-provider')
        self.reception = User.objects.create_user(username='sec-reception', password='password123')
        Group.objects.get_or_create(name='Reception')[0].user_set.add(self.reception)
        self.admin = User.objects.create_user(username='sec-admin', password='password123', is_staff=True)

    def test_gym_member_cannot_read_or_change_gym_data(self):
        self.client.force_login(self.member_user)
        self.assertEqual(self.client.get('/api/fitness/members').status_code, 403)
        self.assertEqual(self.client.get('/api/fitness/payments').status_code, 403)
        created = self.client.post(
            '/api/fitness/members',
            data=json.dumps({
                'first_name': 'Hacker',
                'last_name': 'User',
                'phone': '0600000000',
                'email': '',
                'id_number': 'HACK-1',
                'address': 'x',
            }),
            content_type='application/json',
        )
        self.assertEqual(created.status_code, 403)

    def test_provider_cannot_use_gym_desk(self):
        self.client.force_login(self.provider.user)
        self.assertEqual(self.client.get('/api/fitness/members').status_code, 403)

    def test_reception_can_list_members_but_not_admin_users(self):
        self.client.force_login(self.reception)
        self.assertEqual(self.client.get('/api/fitness/members').status_code, 200)
        self.assertEqual(self.client.get('/api/admin/users').status_code, 403)
        self.assertEqual(self.client.get('/api/fitness/trainers').status_code, 403)


class ClientProviderIdorTests(TestCase):
    def setUp(self):
        self.client_a = make_client(username='client-a', first_name='A', phone='0611111111')
        self.client_b = make_client(username='client-b', first_name='B', phone='0622222222')
        self.provider_a = make_provider(username='prov-a', first_name='ProvA')
        self.provider_b = make_provider(username='prov-b', first_name='ProvB')
        self.admin = make_admin(username='sec-admin2')

    def test_client_cannot_list_or_edit_other_clients(self):
        self.client.force_login(self.client_a.user)
        listed = self.client.get('/api/clients')
        self.assertEqual(listed.status_code, 403)
        other = self.client.get(f'/api/clients/{self.client_b.id}')
        self.assertEqual(other.status_code, 403)
        patched = self.client.patch(
            f'/api/clients/{self.client_b.id}',
            data=json.dumps({'phone': '0699999999'}),
            content_type='application/json',
        )
        self.assertEqual(patched.status_code, 403)
        self.client_b.refresh_from_db()
        self.assertEqual(self.client_b.phone, '0622222222')

    def test_client_can_read_own_profile(self):
        self.client.force_login(self.client_a.user)
        own = self.client.get(f'/api/clients/{self.client_a.id}')
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.json()['id'], self.client_a.id)

    def test_provider_cannot_patch_another_provider(self):
        self.client.force_login(self.provider_a.user)
        response = self.client.patch(
            f'/api/providers/{self.provider_b.id}',
            data=json.dumps({'company_name': 'Stolen'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        listed = self.client.get(f'/api/providers/{self.provider_b.id}')
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()['tax_id'], '')
        self.assertEqual(listed.json()['user']['email'], '')


class NotificationIdorTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username='note-a', is_staff=True)
        self.user_b = User.objects.create_user(username='note-b', is_staff=True)
        self.note_b = GymNotification.objects.create(
            recipient=self.user_b,
            category='members',
            title='Private',
            message='B only',
        )

    def test_user_cannot_read_or_delete_another_users_notification(self):
        self.client.force_login(self.user_a)
        listed = self.client.get('/api/notifications')
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json(), [])
        self.assertEqual(self.client.patch(f'/api/notifications/{self.note_b.id}/read').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/notifications/{self.note_b.id}').status_code, 404)
        self.assertTrue(GymNotification.objects.filter(id=self.note_b.id).exists())


class AdminRoleEscalationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='plain-admin', password='password123', is_staff=True)
        Group.objects.get_or_create(name='Admin')[0].user_set.add(self.admin)
        self.client.force_login(self.admin)

    def test_admin_cannot_promote_to_super_admin(self):
        response = self.client.post(
            '/api/admin/users',
            data=json.dumps({
                'username': 'evil-super',
                'password': 'password123',
                'first_name': 'Evil',
                'last_name': 'Super',
                'email': 'evil@example.com',
                'role': 'Super Admin',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username='evil-super').exists())

    def test_admin_cannot_assign_arbitrary_role(self):
        response = self.client.post(
            '/api/admin/users',
            data=json.dumps({
                'username': 'role-hack',
                'password': 'password123',
                'first_name': 'Role',
                'last_name': 'Hack',
                'email': 'role@example.com',
                'role': 'is_superuser',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class MassAssignmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='self-user', password='password123', is_staff=True)
        self.client.force_login(self.user)

    def test_profile_update_ignores_privilege_fields(self):
        response = self.client.patch(
            '/api/auth/profile',
            data=json.dumps({
                'first_name': 'Self',
                'last_name': 'User',
                'email': 'self@example.com',
                'phone': '0600000000',
                'is_staff': True,
                'is_superuser': True,
                'role': 'Super Admin',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_superuser)
        self.assertNotEqual(self.user.groups.filter(name='Super Admin').count(), 1)


class LoginThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_user(username='lock-me', password='correct-password', is_staff=True)

    def tearDown(self):
        cache.clear()

    def test_repeated_failures_are_limited(self):
        payload = json.dumps({'username': 'lock-me', 'password': 'wrong'})
        last = None
        for _ in range(10):
            last = self.client.post('/api/auth/login', data=payload, content_type='application/json')
            self.assertEqual(last.status_code, 401)
        blocked = self.client.post('/api/auth/login', data=payload, content_type='application/json')
        self.assertEqual(blocked.status_code, 429)


class InactiveSessionTests(TestCase):
    def test_deactivated_user_cannot_keep_using_the_api(self):
        user = User.objects.create_user(username='gone', password='password123', is_staff=True)
        self.client.force_login(user)
        user.is_active = False
        user.save(update_fields=['is_active'])
        response = self.client.get('/api/fitness/members')
        self.assertEqual(response.status_code, 401)


class AuthenticationInputTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='desk-login',
            password='correct-password',
            is_staff=True,
        )

    def tearDown(self):
        cache.clear()

    def test_valid_login_does_not_return_a_password(self):
        response = self.client.post(
            '/api/auth/login',
            data=json.dumps({'username': 'desk-login', 'password': 'correct-password'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn('password', body)
        self.assertEqual(body['username'], 'desk-login')
        self.assertNotIn(b'Traceback', response.content)

    def test_unknown_user_and_wrong_password_are_the_same_401(self):
        missing = self.client.post(
            '/api/auth/login',
            data=json.dumps({'username': 'nobody', 'password': 'correct-password'}),
            content_type='application/json',
        )
        wrong = self.client.post(
            '/api/auth/login',
            data=json.dumps({'username': 'desk-login', 'password': 'nope'}),
            content_type='application/json',
        )
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(missing.json()['detail'], wrong.json()['detail'])

    def test_empty_and_missing_login_fields_are_422(self):
        empty = self.client.post(
            '/api/auth/login',
            data=json.dumps({'username': '', 'password': ''}),
            content_type='application/json',
        )
        missing = self.client.post(
            '/api/auth/login',
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(empty.status_code, 422)
        self.assertEqual(missing.status_code, 422)

    def test_oversized_login_fields_are_rejected(self):
        response = self.client.post(
            '/api/auth/login',
            data=json.dumps({'username': 'a' * 500, 'password': 'b' * 300}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 422)

    def test_malformed_json_does_not_crash(self):
        response = self.client.post(
            '/api/auth/login',
            data='{"username":',
            content_type='application/json',
        )
        self.assertIn(response.status_code, (400, 422))
        self.assertNotIn(b'Traceback', response.content)
        self.assertNotIn(b'DJANGO_SECRET', response.content)

    def test_logout_invalidates_the_session(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/api/auth/me').status_code, 200)
        logout = self.client.post('/api/auth/logout')
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me').status_code, 401)

    def test_password_change_rejects_the_wrong_current_password(self):
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/auth/password',
            data=json.dumps({
                'current_password': 'wrong-password',
                'new_password': 'new-password-123',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('correct-password'))


class CrashAndInjectionTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username='crash-staff', password='password123', is_staff=True)
        self.client.force_login(self.staff)

    def test_sql_injection_in_member_search_does_not_error(self):
        response = self.client.get(
            '/api/fitness/members',
            {'search': "' OR 1=1; DROP TABLE users_clientprofile; --"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.assertNotIn(b'Traceback', response.content)

    def test_invalid_member_id_is_404(self):
        response = self.client.get('/api/fitness/members/999999')
        self.assertEqual(response.status_code, 404)

    def test_negative_payment_amount_is_rejected(self):
        response = self.client.post(
            '/api/fitness/memberships/1/payments',
            data=json.dumps({'amount': '-10.00', 'received_by': 'desk', 'notes': ''}),
            content_type='application/json',
        )
        self.assertIn(response.status_code, (404, 422))
        self.assertNotIn(b'Traceback', response.content)

    def test_wrong_content_type_does_not_crash(self):
        response = self.client.post(
            '/api/fitness/members',
            data='first_name=Hacker',
            content_type='text/plain',
        )
        self.assertIn(response.status_code, (400, 415, 422))
        self.assertNotIn(b'Traceback', response.content)

    def test_duplicate_staff_username_is_409(self):
        payload = {
            'username': 'crash-staff',
            'password': 'password123',
            'first_name': 'Dup',
            'last_name': 'User',
            'email': 'dup@example.com',
            'role': 'Reception',
        }
        response = self.client.post(
            '/api/admin/users',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 409)


class BookingIdorTests(TestCase):
    def setUp(self):
        from datetime import date

        from bookings.services import create_booking
        from bookings.tests.helpers import make_client, make_property, make_provider

        self.client_a = make_client(username='book-client-a', phone='0610000001')
        self.client_b = make_client(username='book-client-b', phone='0610000002')
        self.provider = make_provider(username='book-prov')
        self.property = make_property(self.provider)
        self.booking_b = create_booking(
            client=self.client_b,
            property_obj=self.property,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 11, 1),
        )

    def test_client_cannot_read_another_clients_booking(self):
        self.client.force_login(self.client_a.user)
        detail = self.client.get(f'/api/bookings/{self.booking_b.id}')
        payments = self.client.get(f'/api/bookings/{self.booking_b.id}/payments')
        other_list = self.client.get(f'/api/clients/{self.client_b.id}/bookings')
        filtered = self.client.get('/api/bookings', {'client_id': self.client_b.id})
        self.assertEqual(detail.status_code, 403)
        self.assertEqual(payments.status_code, 403)
        self.assertEqual(other_list.status_code, 403)
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json(), [])


class RoleBoundaryTests(TestCase):
    def setUp(self):
        self.member_user = User.objects.create_user(username='role-member', password='password123')
        ClientProfile.objects.create(user=self.member_user, id_number='ROLE-MEM')
        self.reception = User.objects.create_user(username='role-reception', password='password123')
        Group.objects.get_or_create(name='Reception')[0].user_set.add(self.reception)

    def test_member_cannot_use_admin_user_api(self):
        self.client.force_login(self.member_user)
        listed = self.client.get('/api/admin/users')
        created = self.client.post(
            '/api/admin/users',
            data=json.dumps({
                'username': 'escalated',
                'password': 'password123',
                'first_name': 'Nope',
                'last_name': 'Nope',
                'email': 'nope@example.com',
                'role': 'Admin',
            }),
            content_type='application/json',
        )
        self.assertEqual(listed.status_code, 403)
        self.assertEqual(created.status_code, 403)
        self.assertFalse(User.objects.filter(username='escalated').exists())

    def test_reception_cannot_create_staff_users(self):
        self.client.force_login(self.reception)
        response = self.client.post(
            '/api/admin/users',
            data=json.dumps({
                'username': 'from-reception',
                'password': 'password123',
                'first_name': 'From',
                'last_name': 'Desk',
                'email': 'from@example.com',
                'role': 'Admin',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_member_cannot_open_django_admin(self):
        self.client.force_login(self.member_user)
        response = self.client.get('/admin/')
        self.assertIn(response.status_code, (302, 403))


class CorsAndSecretExposureTests(TestCase):
    def test_untrusted_origin_does_not_receive_cors_credentials(self):
        response = self.client.get('/api/auth/me', HTTP_ORIGIN='https://evil.example')
        self.assertNotEqual(response.get('Access-Control-Allow-Origin'), 'https://evil.example')

    def test_health_and_docs_do_not_leak_secrets(self):
        from django.conf import settings

        health = self.client.get('/healthz')
        docs = self.client.get('/api/docs')
        self.assertEqual(health.status_code, 200)
        self.assertEqual(docs.status_code, 200)
        secret = settings.SECRET_KEY.encode()
        self.assertNotIn(secret, health.content)
        self.assertNotIn(secret, docs.content)
        self.assertNotIn(b'Traceback', docs.content)

    def test_cors_is_not_a_wildcard_with_credentials(self):
        from django.conf import settings

        self.assertTrue(settings.CORS_ALLOW_CREDENTIALS)
        self.assertFalse(getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False))
        self.assertNotIn('*', settings.CORS_ALLOWED_ORIGINS)
