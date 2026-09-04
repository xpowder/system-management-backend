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
