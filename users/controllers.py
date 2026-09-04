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
from users.permissions import ALLOWED_STAFF_ROLES, is_admin

from users.schemas import (
    ClientProfileOut, ClientProfileIn, ClientProfileUpdate,
    ProviderProfileOut, ProviderProfileIn, ProviderProfileUpdate,
    AdminUserIn, AdminUserOut, AdminUserUpdate,
)
from users.models import ClientProfile, ProviderProfile, Property


router = Router(auth=session_auth)


def _require_admin(request):
    group = request.user.groups.first() if request.user.is_authenticated else None
    is_admin_user = request.user.is_authenticated and (request.user.is_superuser or (group is None and request.user.is_staff) or (group is not None and group.name in ['Admin', 'Super Admin']))
    if not is_admin_user:
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


def _owns_provider(request, provider):
    try:
        return request.user.provider_profile.id == provider.id
    except (ObjectDoesNotExist, AttributeError):
        return False


def _require_admin_or_own_client(request, client):
    if is_admin(request.user) or _owns_client(request, client):
        return
    raise HttpError(403, 'You do not have permission to access this client.')


def _require_admin_or_own_provider(request, provider):
    if is_admin(request.user) or _owns_provider(request, provider):
        return
    raise HttpError(403, 'You do not have permission to change this provider.')


def _provider_payload(request, provider):
    payload = ProviderProfileOut.model_validate(provider).model_dump()
    if not (is_admin(request.user) or _owns_provider(request, provider)):
        payload['tax_id'] = ''
        payload['user']['email'] = ''
    return payload


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
    if len(payload.password) < 8:
        raise HttpError(400, 'Password must contain at least 8 characters.')
    role = _assert_assignable_role(request, payload.role) if payload.role else ''
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
    create_gym_notifications('new_staff_user_created', 'system', 'New staff user created', f'{display_name} was added as {role or "User"}.', actor=request.user)
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
        if len(payload.password) < 8:
            raise HttpError(400, 'Password must contain at least 8 characters.')
        user.set_password(payload.password)
    user.save()
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
        create_gym_notifications('user_role_changed', 'system', 'User role changed', f'{display_name} role changed from {previous_role} to {payload_role_label}.', actor=request.user)
    if payload.is_active is False and was_active:
        create_gym_notifications('user_deactivated', 'system', 'User deactivated', f'{display_name} was deactivated.', actor=request.user)
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


# Provider Endpoints
@router.post('/providers', response=ProviderProfileOut)
def create_provider(request, payload: ProviderProfileIn):
    _require_admin(request)
    try:
        user = User.objects.create_user(
            username=f"provider_{payload.email.split('@')[0]}" if payload.email else f"provider_{payload.tax_id or payload.phone or User.objects.count() + 1}",
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email or ""
        )
        provider = ProviderProfile.objects.create(
            user=user,
            phone=payload.phone,
            address=payload.address,
            city=payload.city,
            postal_code=payload.postal_code,
            company_name=payload.company_name,
            tax_id=payload.tax_id
        )
        return provider
    except Exception:
        raise HttpError(400, 'Unable to create provider.')


@router.get('/providers', response=List[ProviderProfileOut])
def list_providers(
    request,
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    queryset = ProviderProfile.objects.select_related('user').all()
    if search:
        queryset = queryset.filter(
            Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(phone__icontains=search)
        )
    return [_provider_payload(request, item) for item in queryset[offset:offset + limit]]


@router.get('/providers/{provider_id}', response=ProviderProfileOut)
def get_provider(request, provider_id: int):
    try:
        provider = ProviderProfile.objects.select_related('user').get(id=provider_id)
    except ProviderProfile.DoesNotExist:
        raise HttpError(404, 'Provider not found')
    return _provider_payload(request, provider)


@router.patch('/providers/{provider_id}', response=ProviderProfileOut)
def update_provider(request, provider_id: int, payload: ProviderProfileUpdate):
    try:
        provider = ProviderProfile.objects.select_related('user').get(id=provider_id)
    except ProviderProfile.DoesNotExist:
        raise HttpError(404, 'Provider not found')
    _require_admin_or_own_provider(request, provider)
    if payload.first_name:
        provider.user.first_name = payload.first_name
    if payload.last_name:
        provider.user.last_name = payload.last_name
    if payload.email:
        provider.user.email = payload.email
    provider.user.save()
    if payload.phone is not None:
        provider.phone = payload.phone
    if payload.address is not None:
        provider.address = payload.address
    if payload.city is not None:
        provider.city = payload.city
    if payload.postal_code is not None:
        provider.postal_code = payload.postal_code
    if payload.company_name is not None:
        provider.company_name = payload.company_name
    if payload.tax_id is not None:
        provider.tax_id = payload.tax_id
    try:
        provider.save()
    except IntegrityError:
        raise HttpError(409, 'A provider with this tax ID already exists.')
    return provider


@router.post('/properties', response={'id': int})
def create_property(request, provider_id: int, name: str, description: str, 
                  property_type: str, address: str, city: str, postal_code: str,
                  monthly_price: float, bedrooms: int = 1, bathrooms: int = 1):
    try:
        provider = ProviderProfile.objects.get(id=provider_id)
    except ProviderProfile.DoesNotExist:
        raise HttpError(404, 'Provider not found')
    _require_admin_or_own_provider(request, provider)
    try:
        property_obj = Property.objects.create(
            provider=provider,
            name=name,
            description=description,
            property_type=property_type,
            address=address,
            city=city,
            postal_code=postal_code,
            monthly_price=monthly_price,
            bedrooms=bedrooms,
            bathrooms=bathrooms
        )
        return {'id': property_obj.id}
    except Exception:
        raise HttpError(400, 'Unable to create property.')


@router.get('/properties', response=List[dict])
def list_properties(
    request,
    provider_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List properties."""
    queryset = Property.objects.filter(is_active=True)
    
    if provider_id:
        queryset = queryset.filter(provider_id=provider_id)
    
    if search:
        queryset = queryset.filter(name__icontains=search) | queryset.filter(
            city__icontains=search
        )
    
    return [
        {
            'id': p.id,
            'provider_id': p.provider_id,
            'name': p.name,
            'city': p.city,
            'property_type': p.property_type,
            'bedrooms': p.bedrooms,
            'bathrooms': p.bathrooms,
            'monthly_price': float(p.monthly_price),
            'is_active': p.is_active,
        }
        for p in queryset[offset:offset + limit]
    ]


@router.get('/properties/{property_id}')
def get_property(request, property_id: int):
    try:
        property_obj = Property.objects.get(id=property_id)
    except Property.DoesNotExist:
        raise HttpError(404, 'Property not found')
    data = {
        'id': property_obj.id,
        'name': property_obj.name,
        'description': property_obj.description,
        'city': property_obj.city,
        'property_type': property_obj.property_type,
        'bedrooms': property_obj.bedrooms,
        'bathrooms': property_obj.bathrooms,
        'monthly_price': float(property_obj.monthly_price),
    }
    if is_admin(request.user) or _owns_provider(request, property_obj.provider):
        data['address'] = property_obj.address
    return data
