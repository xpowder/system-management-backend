import secrets

from django.db import models
from django.contrib.auth.models import User
from core.models import BaseModel


def generate_qr_token():
    """Opaque membership-card token. Not derived from the member id or PII."""
    return secrets.token_urlsafe(32)


class UserRole(models.TextChoices):
    """User role choices."""
    ADMIN = 'admin', 'Administrator'
    PROVIDER = 'provider', 'Provider'
    CLIENT = 'client', 'Client'


class StaffProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f'{self.user.username} staff profile'


class ClientProfile(BaseModel):
    """Client profile model."""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Morocco')
    postal_code = models.CharField(max_length=20, blank=True)
    id_number = models.CharField(max_length=50, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    qr_token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_qr_token,
        editable=False,
        help_text='Opaque token encoded in the member QR card. Not a login credential.',
    )
    
    class Meta:
        ordering = ['user__first_name', 'user__last_name']
        verbose_name = 'Client Profile'
        verbose_name_plural = 'Client Profiles'
        indexes = [models.Index(fields=['is_active'])]
    
    def save(self, *args, **kwargs):
        if not self.qr_token:
            self.qr_token = generate_qr_token()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} (Client)"


class ProviderProfile(BaseModel):
    """Provider profile model."""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='provider_profile')
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Morocco')
    postal_code = models.CharField(max_length=20, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    tax_id = models.CharField(max_length=50, unique=True, blank=True)
    
    class Meta:
        ordering = ['user__first_name', 'user__last_name']
        verbose_name = 'Provider Profile'
        verbose_name_plural = 'Provider Profiles'
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} (Provider)"


class Property(BaseModel):
    """Property/listing model."""
    
    PROPERTY_TYPE_CHOICES = [
        ('apartment', 'Apartment'),
        ('house', 'House'),
        ('villa', 'Villa'),
        ('room', 'Room'),
        ('other', 'Other'),
    ]
    
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name='properties')
    name = models.CharField(max_length=200)
    description = models.TextField()
    property_type = models.CharField(max_length=50, choices=PROPERTY_TYPE_CHOICES)
    
    # Address
    address = models.TextField()
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='Morocco')
    postal_code = models.CharField(max_length=20)
    
    # Features
    bedrooms = models.IntegerField(default=1)
    bathrooms = models.IntegerField(default=1)
    square_meters = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Pricing
    monthly_price = models.DecimalField(max_digits=15, decimal_places=2, help_text="Price in MAD")
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['provider', 'name']
        verbose_name = 'Property'
        verbose_name_plural = 'Properties'
    
    def __str__(self):
        return f"{self.name} ({self.city})"

