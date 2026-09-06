import json

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from unittest.mock import patch

from bookings.tests.helpers import make_admin, make_client, make_provider
from fitness.models import GymExpense, GymNotification, Membership, MembershipPlan
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

    def test_provider_http_is_unmounted(self):
        self.client.force_login(self.provider_a.user)
        self.assertEqual(self.client.get('/api/providers').status_code, 404)
        self.assertEqual(self.client.get(f'/api/providers/{self.provider_b.id}').status_code, 404)
        patched = self.client.patch(
            f'/api/providers/{self.provider_b.id}',
            data=json.dumps({'company_name': 'Stolen'}),
            content_type='application/json',
        )
        self.assertEqual(patched.status_code, 404)


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
        for _ in range(9):
            last = self.client.post('/api/auth/login', data=payload, content_type='application/json')
            self.assertEqual(last.status_code, 401)
        blocked = self.client.post('/api/auth/login', data=payload, content_type='application/json')
        self.assertEqual(blocked.status_code, 429)

    def test_successful_login_clears_failures(self):
        wrong = json.dumps({'username': 'lock-me', 'password': 'wrong'})
        for _ in range(5):
            self.assertEqual(
                self.client.post('/api/auth/login', data=wrong, content_type='application/json').status_code,
                401,
            )
        ok = self.client.post(
            '/api/auth/login',
            data=json.dumps({'username': 'lock-me', 'password': 'correct-password'}),
            content_type='application/json',
        )
        self.assertEqual(ok.status_code, 200)
        self.client.post('/api/auth/logout')
        again = self.client.post('/api/auth/login', data=wrong, content_type='application/json')
        self.assertEqual(again.status_code, 401)

    def test_lockout_recovers_when_the_counter_expires(self):
        payload = json.dumps({'username': 'lock-me', 'password': 'wrong'})
        for _ in range(10):
            self.client.post('/api/auth/login', data=payload, content_type='application/json')
        self.assertEqual(
            self.client.post('/api/auth/login', data=payload, content_type='application/json').status_code,
            429,
        )
        cache.clear()
        recovered = self.client.post('/api/auth/login', data=payload, content_type='application/json')
        self.assertEqual(recovered.status_code, 401)

    def test_failure_counter_increments_for_concurrent_style_calls(self):
        from core.lockout import account_key, record_failure

        record_failure('127.0.0.1', 'lock-me')
        record_failure('127.0.0.1', 'lock-me')
        self.assertEqual(int(cache.get(account_key('127.0.0.1', 'lock-me'))), 2)

    def test_other_staff_are_not_locked_by_one_username(self):
        User.objects.create_user(username='other-desk', password='correct-password', is_staff=True)
        payload = json.dumps({'username': 'lock-me', 'password': 'wrong'})
        for _ in range(10):
            self.client.post('/api/auth/login', data=payload, content_type='application/json')
        other = self.client.post(
            '/api/auth/login',
            data=json.dumps({'username': 'other-desk', 'password': 'wrong'}),
            content_type='application/json',
        )
        self.assertEqual(other.status_code, 401)

    @patch('core.lockout.IP_LIMIT', 3)
    def test_ip_spray_is_limited_without_permanent_lock(self):
        for index in range(3):
            User.objects.create_user(username=f'spray-{index}', password='correct-password', is_staff=True)
            response = self.client.post(
                '/api/auth/login',
                data=json.dumps({'username': f'spray-{index}', 'password': 'wrong'}),
                content_type='application/json',
            )
            self.assertIn(response.status_code, (401, 429))
        blocked = self.client.post(
            '/api/auth/login',
            data=json.dumps({'username': 'lock-me', 'password': 'wrong'}),
            content_type='application/json',
        )
        self.assertEqual(blocked.status_code, 429)
        cache.clear()
        recovered = self.client.post(
            '/api/auth/login',
            data=json.dumps({'username': 'lock-me', 'password': 'correct-password'}),
            content_type='application/json',
        )
        self.assertEqual(recovered.status_code, 200)

    def test_spoofed_forwarded_for_does_not_reset_local_lockout(self):
        payload = json.dumps({'username': 'lock-me', 'password': 'wrong'})
        for index in range(9):
            response = self.client.post(
                '/api/auth/login',
                data=payload,
                content_type='application/json',
                HTTP_X_FORWARDED_FOR=f'203.0.113.{index}',
            )
            self.assertEqual(response.status_code, 401)
        blocked = self.client.post(
            '/api/auth/login',
            data=payload,
            content_type='application/json',
            HTTP_X_FORWARDED_FOR='198.51.100.10',
        )
        self.assertEqual(blocked.status_code, 429)

    @override_settings(USE_HTTPS=True)
    def test_lockout_behind_a_proxy_is_per_client_ip(self):
        payload = json.dumps({'username': 'lock-me', 'password': 'wrong'})
        for _ in range(10):
            self.client.post(
                '/api/auth/login',
                data=payload,
                content_type='application/json',
                HTTP_X_FORWARDED_FOR='203.0.113.10',
            )
        blocked = self.client.post(
            '/api/auth/login',
            data=payload,
            content_type='application/json',
            HTTP_X_FORWARDED_FOR='203.0.113.10',
        )
        other = self.client.post(
            '/api/auth/login',
            data=payload,
            content_type='application/json',
            HTTP_X_FORWARDED_FOR='203.0.113.20',
        )
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(other.status_code, 401)


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

    def test_password_change_rejects_a_common_password(self):
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/auth/password',
            data=json.dumps({
                'current_password': 'correct-password',
                'new_password': 'password123',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('correct-password'))

    def test_password_change_invalidates_other_sessions(self):
        other = Client()
        self.client.force_login(self.user)
        other.force_login(self.user)
        self.assertEqual(self.client.get('/api/auth/me').status_code, 200)
        self.assertEqual(other.get('/api/auth/me').status_code, 200)
        changed = self.client.post(
            '/api/auth/password',
            data=json.dumps({
                'current_password': 'correct-password',
                'new_password': 'DeskPass-2026!',
            }),
            content_type='application/json',
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me').status_code, 200)
        self.assertEqual(other.get('/api/auth/me').status_code, 401)


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
        self.assertIn(response.status_code, (400, 404, 422))
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


class BookingApiPausedTests(TestCase):
    def test_booking_http_apis_are_unavailable(self):
        staff = User.objects.create_user(username='book-paused', password='password123', is_staff=True)
        self.client.force_login(staff)
        for path in (
            '/api/bookings',
            '/api/dashboard',
            '/api/providers',
            '/api/properties',
            '/api/reports/revenue',
        ):
            self.assertEqual(self.client.get(path).status_code, 404, path)


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

    def test_named_admin_group_can_use_staff_admin_api(self):
        staff = User.objects.create_user(username='group-admin', password='password123', is_staff=True)
        Group.objects.get_or_create(name='Admin')[0].user_set.add(staff)
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/api/admin/users').status_code, 200)

    def test_staff_cannot_open_django_admin(self):
        staff = User.objects.create_user(username='role-staff', password='password123', is_staff=True)
        self.client.force_login(staff)
        response = self.client.get('/admin/')
        self.assertIn(response.status_code, (302, 403))

    def test_superuser_can_open_django_admin(self):
        superuser = User.objects.create_superuser(
            username='role-super',
            email='role-super@example.com',
            password='password123',
        )
        self.client.force_login(superuser)
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)


class GymDeskPermissionTests(TestCase):
    def setUp(self):
        self.member_user = User.objects.create_user(username='perm-member', password='password123')
        self.member = ClientProfile.objects.create(user=self.member_user, id_number='PERM-MEM')
        self.reception = User.objects.create_user(username='perm-reception', password='password123')
        Group.objects.get_or_create(name='Reception')[0].user_set.add(self.reception)
        self.trainer_login = User.objects.create_user(username='perm-trainer', password='password123')
        Group.objects.get_or_create(name='Trainer')[0].user_set.add(self.trainer_login)
        self.admin = User.objects.create_user(username='perm-admin', password='password123', is_staff=True)
        plan = MembershipPlan.objects.create(name='Monthly', duration_months=1, price=10)
        self.membership = Membership.objects.create(
            member=self.member,
            plan=plan,
            start_date='2026-01-01',
            end_date='2026-02-01',
            price=10,
        )
        self.expense = GymExpense.objects.create(
            category='water',
            title='Water',
            amount=20,
            year=2026,
            month=1,
        )

    def test_unauthenticated_sensitive_routes_are_401(self):
        for method, path in (
            ('delete', f'/api/fitness/members/{self.member.id}'),
            ('delete', f'/api/fitness/memberships/{self.membership.id}'),
            ('delete', f'/api/fitness/expenses/{self.expense.id}'),
            ('delete', f'/api/admin/users/{self.admin.id}'),
            ('get', '/api/fitness/reports/overview'),
            ('get', '/api/notifications'),
        ):
            response = getattr(self.client, method)(path)
            self.assertEqual(response.status_code, 401, path)

    def test_gym_member_sensitive_routes_are_403(self):
        self.client.force_login(self.member_user)
        self.assertEqual(self.client.delete(f'/api/fitness/members/{self.member.id}').status_code, 403)
        self.assertEqual(self.client.get(f'/api/fitness/members/{self.member.id}').status_code, 403)
        self.assertEqual(self.client.get('/api/fitness/payments').status_code, 403)
        self.assertEqual(self.client.get('/api/fitness/reports/overview').status_code, 403)
        self.assertTrue(ClientProfile.objects.filter(id=self.member.id, is_active=True).exists())

    def test_trainer_login_cannot_use_gym_desk(self):
        self.client.force_login(self.trainer_login)
        self.assertEqual(self.client.get('/api/auth/me').status_code, 200)
        self.assertEqual(self.client.get('/api/fitness/members').status_code, 403)

    def test_reception_can_run_desk_work_but_not_admin_finance(self):
        self.client.force_login(self.reception)
        self.assertEqual(self.client.get('/api/fitness/members').status_code, 200)
        self.assertEqual(self.client.get(f'/api/fitness/members/{self.member.id}').status_code, 200)
        self.assertEqual(self.client.get('/api/fitness/payments').status_code, 200)
        self.assertEqual(self.client.get('/api/fitness/reports/classes').status_code, 200)
        self.assertEqual(self.client.get('/api/fitness/reports/overview').status_code, 403)
        self.assertEqual(self.client.get('/api/fitness/expenses').status_code, 403)
        self.assertEqual(self.client.delete(f'/api/fitness/expenses/{self.expense.id}').status_code, 403)
        self.assertEqual(self.client.get('/api/fitness/trainers').status_code, 403)
        deactivated = self.client.delete(f'/api/fitness/members/{self.member.id}')
        self.assertEqual(deactivated.status_code, 200)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)
        self.assertTrue(GymExpense.objects.filter(id=self.expense.id).exists())


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
