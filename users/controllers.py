"""
User API controllers using Django Ninja.
"""
from typing import List, Optional

from ninja import Router, Query
from ninja.errors import HttpError
from django.contrib.auth.models import Group, User
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.db.models import Q

from core.auth import session_auth
from core.sessions import flush_user_sessions
from users.passwords import require_strong_password
from users.permissions import ALLOWED_STAFF_ROLES, is_admin

from users.schemas import (
    ClientProfileOut, ClientProfileIn, ClientProfileUpdate,
    AdminUserIn, AdminUserOut, AdminUserUpdate,
)
from users.models import ClientProfile


router = Router(auth=session_auth)


def _require_admin(request):
    if not is_admin(request.user):
        raise HttpError(403, "You don't have permission to access Administration.")


def _staff_user_queryset():
    return User.objects.filter(
        Q(is_staff=True) | Q(is_superuser=True) | Q(groups__name__in=['Super Admin', 'Admin', 'Reception', 'Trainer'])
    ).distinct()


def _get_managed_staff_user(request, user_id):
    try:
        user = _staff_user_queryset().get(id=user_id)
    except User.DoesNotExist:
        raise HttpError(404, 'User not found.')
    if user.is_superuser and not request.user.is_superuser:
        raise HttpError(403, 'Only a Super Admin can change a Super Admin account.')
    return user


def _normalize_staff_role(role: str) -> str:
    mapping = {
        'superadmin': 'Super Admin',
        'super admin': 'Super Admin',
        'admin': 'Admin',
        'reception': 'Reception',
        'trainer': 'Trainer',
    }
    cleaned = (role or '').strip()
    if not cleaned:
        return ''
    return mapping.get(cleaned.lower(), cleaned)


def _assert_assignable_role(request, role: str) -> str:
    role = _normalize_staff_role(role)
    if role not in ALLOWED_STAFF_ROLES:
        raise HttpError(400, 'Role must be Reception, Trainer, Admin, or Super Admin.')
    if role == 'Super Admin' and not request.user.is_superuser:
        raise HttpError(403, 'Only a Super Admin can assign the Super Admin role.')
    return role


def _owns_client(request, client):
    try:
        return request.user.client_profile.id == client.id
    except (ObjectDoesNotExist, AttributeError):
        return False


def _require_admin_or_own_client(request, client):
    if is_admin(request.user) or _owns_client(request, client):
        return
    raise HttpError(403, 'You do not have permission to access this client.')


def _admin_user_data(user):
    role = user.groups.first().name if user.groups.exists() else ('Super Admin' if user.is_superuser else 'Admin' if user.is_staff else 'User')
    return {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'role': role,
        'last_login': user.last_login,
        'date_joined': user.date_joined,
    }


@router.get('/admin/users', response=List[AdminUserOut])
def list_admin_users(request, search: Optional[str] = None):
    _require_admin(request)
    queryset = _staff_user_queryset().prefetch_related('groups').order_by('first_name', 'last_name', 'username')
    if search:
        queryset = queryset.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search) | Q(username__icontains=search))
    return [_admin_user_data(user) for user in queryset[:500]]


@router.post('/admin/users', response=AdminUserOut)
def create_admin_user(request, payload: AdminUserIn):
    _require_admin(request)
    if User.objects.filter(username=payload.username).exists():
        raise HttpError(409, 'This username is already in use.')
    role = _assert_assignable_role(request, payload.role) if payload.role else ''
    require_strong_password(payload.password)
    is_super_admin = role == 'Super Admin'
    is_admin_role = role in ('Admin', 'Super Admin')
    try:
        user = User.objects.create_user(username=payload.username, password=payload.password, first_name=payload.first_name, last_name=payload.last_name, email=payload.email, is_staff=is_admin_role, is_superuser=is_super_admin)
    except IntegrityError:
        raise HttpError(409, 'This username is already in use.')
    if role:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    from fitness.controllers import create_gym_notifications
    display_name = user.get_full_name() or user.username
    create_gym_notifications('new_staff_user_created', 'system', 'New staff user created', f'{display_name} was added as {role or "User"}.', actor=request.user, admin_only=True)
    return _admin_user_data(user)


@router.patch('/admin/users/{user_id}', response=AdminUserOut)
def update_admin_user(request, user_id: int, payload: AdminUserUpdate):
    _require_admin(request)
    user = _get_managed_staff_user(request, user_id)
    previous_role = user.groups.first().name if user.groups.exists() else ('Super Admin' if user.is_superuser else 'Admin' if user.is_staff else 'User')
    was_active = user.is_active
    for field in ('first_name', 'last_name', 'email', 'is_active'):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)
    if payload.password is not None:
        require_strong_password(payload.password, user=user)
        user.set_password(payload.password)
    user.save()
    if payload.password is not None:
        flush_user_sessions(user)
    if payload.role is not None:
        role = _assert_assignable_role(request, payload.role) if payload.role else ''
        user.groups.clear()
        if role:
            user.groups.add(Group.objects.get_or_create(name=role)[0])
        is_super_admin = role == 'Super Admin'
        user.is_staff = role in ('Admin', 'Super Admin') or user.is_superuser
        user.is_superuser = is_super_admin
        user.save(update_fields=['is_staff', 'is_superuser'])
        payload_role_label = role
    else:
        payload_role_label = previous_role
    display_name = user.get_full_name() or user.username
    from fitness.controllers import create_gym_notifications
    if payload.role is not None and payload_role_label != previous_role:
        create_gym_notifications('user_role_changed', 'system', 'User role changed', f'{display_name} role changed from {previous_role} to {payload_role_label}.', actor=request.user, admin_only=True)
    if payload.is_active is False and was_active:
        create_gym_notifications('user_deactivated', 'system', 'User deactivated', f'{display_name} was deactivated.', actor=request.user, admin_only=True)
    return _admin_user_data(user)


@router.delete('/admin/users/{user_id}')
def delete_admin_user(request, user_id: int):
    _require_admin(request)
    if request.user.id == user_id:
        raise HttpError(400, 'You cannot delete your own account.')
    user = _get_managed_staff_user(request, user_id)
    if user.is_superuser and User.objects.filter(is_superuser=True, is_active=True).count() <= 1:
        raise HttpError(400, 'You cannot delete the last Super Admin.')
    user.delete()
    return {'success': True}


# Client Endpoints
@router.post('/clients', response=ClientProfileOut)
def create_client(request, payload: ClientProfileIn):
    _require_admin(request)
    try:
        user = User.objects.create_user(
            username=f"client_{payload.email.split('@')[0]}" if payload.email else f"client_{payload.id_number or payload.phone or User.objects.count() + 1}",
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email or ""
        )
        client = ClientProfile.objects.create(
            user=user,
            phone=payload.phone,
            address=payload.address,
            city=payload.city,
            postal_code=payload.postal_code,
            id_number=payload.id_number
        )
        return client
    except Exception:
        raise HttpError(400, 'Unable to create client.')


@router.get('/clients', response=List[ClientProfileOut])
def list_clients(
    request,
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    _require_admin(request)
    queryset = ClientProfile.objects.select_related('user').all()
    if search:
        queryset = queryset.filter(
            Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(phone__icontains=search)
        )
    return list(queryset[offset:offset + limit])


@router.get('/clients/{client_id}', response=ClientProfileOut)
def get_client(request, client_id: int):
    try:
        client = ClientProfile.objects.select_related('user').get(id=client_id)
    except ClientProfile.DoesNotExist:
        raise HttpError(404, 'Client not found')
    _require_admin_or_own_client(request, client)
    return client


@router.patch('/clients/{client_id}', response=ClientProfileOut)
def update_client(request, client_id: int, payload: ClientProfileUpdate):
    try:
        client = ClientProfile.objects.select_related('user').get(id=client_id)
    except ClientProfile.DoesNotExist:
        raise HttpError(404, 'Client not found')
    _require_admin_or_own_client(request, client)
    if payload.first_name:
        client.user.first_name = payload.first_name
    if payload.last_name:
        client.user.last_name = payload.last_name
    if payload.email:
        client.user.email = payload.email
    client.user.save()
    if payload.phone is not None:
        client.phone = payload.phone
    if payload.address is not None:
        client.address = payload.address
    if payload.city is not None:
        client.city = payload.city
    if payload.postal_code is not None:
        client.postal_code = payload.postal_code
    if payload.id_number is not None:
        client.id_number = payload.id_number
    try:
        client.save()
    except IntegrityError:
        raise HttpError(409, 'A client with this identity already exists.')
    return client
