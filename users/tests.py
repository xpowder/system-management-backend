import json

from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from django.test import TestCase


class AdminUserApiTest(TestCase):
	def setUp(self):
		self.admin = User.objects.create_user(username='admin-user', password='password123', is_staff=True)
		self.target = User.objects.create_user(username='target-user', password='password123', first_name='Target')

	def test_user_list_requires_staff(self):
		response = self.client.get('/api/admin/users')
		self.assertEqual(response.status_code, 401)

	def test_staff_can_create_update_deactivate_and_delete_user(self):
		self.client.force_login(self.admin)
		create = self.client.post('/api/admin/users', data=json.dumps({
			'username': 'new-user',
			'password': 'password123',
			'first_name': 'New',
			'last_name': 'User',
			'email': 'new@example.com',
			'role': 'Reception',
		}), content_type='application/json')
		self.assertEqual(create.status_code, 200)
		user_id = create.json()['id']
		self.assertEqual(create.json()['role'], 'Reception')
		self.assertFalse(User.objects.get(id=user_id).is_staff)

		update = self.client.patch(f'/api/admin/users/{user_id}', data=json.dumps({
			'first_name': 'Updated',
			'is_active': False,
			'role': 'Trainer',
		}), content_type='application/json')
		self.assertEqual(update.status_code, 200)
		self.assertFalse(User.objects.get(id=user_id).is_active)
		self.assertEqual(update.json()['role'], 'Trainer')

		password_update = self.client.patch(f'/api/admin/users/{user_id}', data=json.dumps({
			'password': 'new-password-123',
		}), content_type='application/json')
		self.assertEqual(password_update.status_code, 200)
		self.assertTrue(User.objects.get(id=user_id).check_password('new-password-123'))

		delete = self.client.delete(f'/api/admin/users/{user_id}')
		self.assertEqual(delete.status_code, 200)
		self.assertFalse(User.objects.filter(id=user_id).exists())

	def test_staff_cannot_delete_own_account(self):
		self.client.force_login(self.admin)
		response = self.client.delete(f'/api/admin/users/{self.admin.id}')
		self.assertEqual(response.status_code, 400)

	def test_superuser_can_access_administration(self):
		superuser = User.objects.create_superuser(username='super-user', password='password123')
		self.client.force_login(superuser)
		response = self.client.get('/api/admin/users')
		self.assertEqual(response.status_code, 200)

	def test_administration_lists_staff_roles_not_gym_members(self):
		reception = User.objects.create_user(username='reception-user', password='password123')
		reception.groups.add(Group.objects.create(name='Reception'))
		member = User.objects.create_user(username='gym-member', password='password123')
		self.client.force_login(self.admin)
		usernames = [item['username'] for item in self.client.get('/api/admin/users').json()]
		self.assertIn(reception.username, usernames)
		self.assertNotIn(member.username, usernames)
