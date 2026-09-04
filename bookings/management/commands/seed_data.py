"""
Management command to seed initial data for testing.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import ClientProfile, ProviderProfile, Property
from bookings.models import Booking, BookingStatus, PaymentStatus
from fitness.models import FitnessClassType, Membership, MembershipPlan, TrainingClass
from datetime import date, timedelta
from decimal import Decimal


class Command(BaseCommand):
    help = 'Seeds the database with sample data for testing'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Creating sample data...'))
        
        # Create admin user
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'first_name': 'Admin',
                'last_name': 'User',
                'email': 'admin@homezup.local',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if _:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('Created admin user (username: admin, password: admin123)'))
        
        # Create sample clients
        clients = []
        client_data = [
            ('Ahmed', 'Hassan', '0612345678'),
            ('Fatima', 'Ali', '0623456789'),
            ('Mohamed', 'Karim', '0634567890'),
        ]
        
        for first_name, last_name, phone in client_data:
            user, created = User.objects.get_or_create(
                username=f'client_{first_name.lower()}',
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f'{first_name.lower()}@example.com'
                }
            )
            
            if created:
                user.set_password('password123')
                user.save()
            
            client, _ = ClientProfile.objects.get_or_create(
                user=user,
                defaults={
                    'phone': phone,
                    'address': f'{first_name}\'s Address',
                    'city': 'Casablanca',
                    'postal_code': '20000',
                    'id_number': f'ID{first_name.upper()[:3]}001'
                }
            )
            clients.append(client)
        
        self.stdout.write(self.style.SUCCESS(f'Created {len(clients)} sample clients'))
        
        # Create sample providers
        providers = []
        provider_data = [
            ('Hassan', 'Properties', '0612111111'),
            ('Karim', 'Real Estate', '0612222222'),
        ]
        
        for first_name, company, phone in provider_data:
            user, created = User.objects.get_or_create(
                username=f'provider_{first_name.lower()}',
                defaults={
                    'first_name': first_name,
                    'last_name': 'Provider',
                    'email': f'{first_name.lower()}provider@example.com'
                }
            )
            
            if created:
                user.set_password('password123')
                user.save()
            
            provider, _ = ProviderProfile.objects.get_or_create(
                user=user,
                defaults={
                    'phone': phone,
                    'address': f'{company} HQ',
                    'city': 'Casablanca',
                    'postal_code': '20000',
                    'company_name': company,
                    'tax_id': f'TAX{first_name.upper()[:3]}001'
                }
            )
            providers.append(provider)
        
        self.stdout.write(self.style.SUCCESS(f'Created {len(providers)} sample providers'))
        
        # Create sample properties
        properties = []
        property_data = [
            ('Apartment A12', 'Modern apartment in Casablanca', 'apartment', 3, 2, Decimal('5000.00')),
            ('Villa B20', 'Luxury villa with garden', 'villa', 4, 3, Decimal('8000.00')),
            ('Room C101', 'Single room with bathroom', 'room', 1, 1, Decimal('1500.00')),
        ]
        
        for i, (name, description, prop_type, bedrooms, bathrooms, price) in enumerate(property_data):
            prop, _ = Property.objects.get_or_create(
                name=name,
                provider=providers[i % len(providers)],
                defaults={
                    'description': description,
                    'property_type': prop_type,
                    'address': f'Street {i+1}, Casablanca',
                    'city': 'Casablanca',
                    'postal_code': '20000',
                    'bedrooms': bedrooms,
                    'bathrooms': bathrooms,
                    'monthly_price': price,
                    'is_active': True
                }
            )
            properties.append(prop)
        
        self.stdout.write(self.style.SUCCESS(f'Created {len(properties)} sample properties'))
        
        # Create sample bookings
        today = date.today()
        bookings_created = 0
        
        for i, client in enumerate(clients):
            prop = properties[i % len(properties)]
            provider = prop.provider
            
            start_date = today + timedelta(days=10)
            end_date = start_date + timedelta(days=60)  # 2 months
            
            booking, created = Booking.objects.get_or_create(
                client=client,
                provider=provider,
                property_ref=prop,
                start_date=start_date,
                defaults={
                    'end_date': end_date,
                    'monthly_price': prop.monthly_price,
                    'number_of_months': 2,
                    'total_price': prop.monthly_price * 2,
                    'status': BookingStatus.PENDING,
                    'payment_status': PaymentStatus.UNPAID
                }
            )
            
            if created:
                bookings_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'Created {bookings_created} sample bookings'))

        fitness_classes = [
            ('Boxing Team', FitnessClassType.BOXING),
            ('Musculation Team', FitnessClassType.MUSCULATION),
            ('Aerobic Team', FitnessClassType.AEROBIC),
            ('Kick Boxing Team', FitnessClassType.KICK_BOXING),
        ]
        for name, class_type in fitness_classes:
            TrainingClass.objects.get_or_create(
                name=name,
                class_type=class_type,
                defaults={'price_per_member': Decimal('150.00') if class_type == FitnessClassType.MUSCULATION else Decimal('100.00')},
            )
        self.stdout.write(self.style.SUCCESS('Created 4 fitness classes at 100.00 MAD per member'))

        plans = [
            ('Monthly', 1, Decimal('120.00')),
            ('3 Months', 3, Decimal('800.00')),
            ('6 Months', 6, Decimal('1500.00')),
            ('Yearly', 12, Decimal('2500.00')),
        ]
        for name, duration_months, price in plans:
            MembershipPlan.objects.get_or_create(
                name=name,
                defaults={'duration_months': duration_months, 'price': price},
            )
        self.stdout.write(self.style.SUCCESS('Created 4 membership plans'))

        monthly_plan = MembershipPlan.objects.get(name='Monthly')
        membership_start = date.today()
        for client in clients:
            Membership.objects.get_or_create(
                member=client,
                plan=monthly_plan,
                start_date=membership_start,
                defaults={
                    'end_date': membership_start + timedelta(days=30),
                    'price': monthly_plan.price,
                },
            )
        self.stdout.write(self.style.SUCCESS('Created active memberships for sample clients'))
        
        self.stdout.write(self.style.SUCCESS('Sample data created successfully!'))
        self.stdout.write(
            self.style.WARNING(
                'You can now access the admin panel at http://127.0.0.1:8000/admin '
                'with username "admin" and password "admin123"'
            )
        )
