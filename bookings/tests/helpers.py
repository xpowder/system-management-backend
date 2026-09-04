from decimal import Decimal

from django.contrib.auth.models import User

from users.models import ClientProfile, Property, ProviderProfile


def make_admin(username="admin"):
    return User.objects.create_superuser(
        username=username,
        email=f"{username}@homezup.local",
        password="admin123",
        first_name="Admin",
        last_name="User",
    )


def make_provider(username="provider1", first_name="Hassan"):
    user = User.objects.create_user(
        username=username,
        password="password123",
        first_name=first_name,
        last_name="Provider",
        email=f"{username}@example.com",
    )
    return ProviderProfile.objects.create(
        user=user,
        company_name=f"{first_name} Properties",
        phone="0611111111",
        tax_id=f"TAX-{username}",
    )


def make_client(username="client1", first_name="Ahmed", phone="0612345678"):
    user = User.objects.create_user(
        username=username,
        password="password123",
        first_name=first_name,
        last_name="Hassan",
        email=f"{username}@example.com",
    )
    return ClientProfile.objects.create(
        user=user,
        phone=phone,
        city="Casablanca",
        id_number=f"ID-{username}",
    )


def make_property(provider, name="Apartment A12", monthly_price="5000.00"):
    return Property.objects.create(
        provider=provider,
        name=name,
        description="Test property",
        property_type="apartment",
        address="12 Test Street",
        city="Casablanca",
        postal_code="20000",
        monthly_price=Decimal(monthly_price),
    )
