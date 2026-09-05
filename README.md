# FlexOper gym (this PC)

**Hand this computer over with [DELIVER.md](DELIVER.md).** That file has start/stop, roles, backup, a live checklist, and who to call.

Daily start: `start.bat` then `start-frontend.bat`.  
One-port start after a build: `deliver.bat`.  
Backup: `backup.bat`.

---

# Homezup Local Booking Management System

A Django-based local PC application for managing property bookings, payments, and client/provider information. Built with Django, Django Ninja Extra, and SQLite.

## Features

- ✅ Complete booking management system
- ✅ Cash payment tracking with receipts
- ✅ Property availability management
- ✅ Client and provider profiles
- ✅ Booking status lifecycle (Pending → Approved → Active → Completed)
- ✅ Dashboard with real-time statistics
- ✅ Monthly revenue and occupancy reports
- ✅ Django admin interface
- ✅ RESTful API with Django Ninja Extra
- ✅ Database backup functionality
- ✅ Local SQLite database

## Installation

### Prerequisites
- Python 3.13+
- pip (Python package manager)

### Setup

1. **Create Virtual Environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Migrations**
   ```bash
   python manage.py migrate
   ```

4. **Create Superuser (Admin)**
   ```bash
   python manage.py createsuperuser
   ```
   Choose your own staff username and a strong password. Do not reuse a shared default password.

5. **Start Development Server**
   ```bash
   python manage.py runserver
   ```

   Access the application at `http://127.0.0.1:8000`

## Usage

### Admin Interface
Access Django admin at: `http://127.0.0.1:8000/admin`

- Manage clients, providers, and properties
- View and manage bookings
- Track payments
- View booking history

### API Endpoints

The API is available at `http://127.0.0.1:8000/api/` with the following endpoints:

#### Bookings
- `POST /api/bookings/` - Create a new booking
- `GET /api/bookings/` - List all bookings (with filters)
- `GET /api/bookings/{id}/` - Get booking details
- `PATCH /api/bookings/{id}/` - Update booking
- `POST /api/bookings/{id}/approve` - Approve a booking
- `POST /api/bookings/{id}/reject` - Reject a booking
- `POST /api/bookings/{id}/cancel` - Cancel a booking

#### Payments
- `GET /api/bookings/{id}/payments/` - Get payment history
- `POST /api/bookings/{id}/payments` - Record cash payment

#### Dashboard & Reports
- `GET /api/dashboard/` - Get dashboard statistics
- `GET /api/reports/outstanding/` - Get outstanding payments
- `GET /api/reports/occupancy/` - Get occupancy report

#### Properties
- `GET /api/properties/{id}/availability?start_date=2026-10-01&end_date=2026-12-01` - Check availability

#### Clients
- `POST /api/clients/` - Create client
- `GET /api/clients/` - List clients
- `GET /api/clients/{id}/` - Get client details
- `PATCH /api/clients/{id}/` - Update client

#### Providers
- `POST /api/providers/` - Create provider
- `GET /api/providers/` - List providers
- `GET /api/providers/{id}/` - Get provider details
- `PATCH /api/providers/{id}/` - Update provider

#### Properties
- `POST /api/properties/` - Create property
- `GET /api/properties/` - List properties
- `GET /api/properties/{id}/` - Get property details

## Database

The system uses **SQLite** (`db.sqlite3`) for local data storage.

### Backup Database
```bash
python manage.py backup_database
```

Backups are saved in `backups/` directory with timestamp: `db_YYYY-MM-DD_HH-MM-SS.sqlite3`

## Management Commands

### Update Booking Statuses
```bash
python manage.py update_booking_statuses
```
Automatically transitions bookings:
- APPROVED → ACTIVE (when start_date reached)
- ACTIVE → COMPLETED (when end_date reached)

### Seed Sample Data
```bash
python manage.py seed_data
```
Creates sample clients, providers, properties, and bookings for testing.

### Backup Database
```bash
python manage.py backup_database
```
Creates a timestamped backup of the SQLite database.

## Models

### Booking
- Tracks property bookings
- Fields: client, provider, property, dates, pricing, status, payment_status
- Statuses: PENDING, APPROVED, ACTIVE, COMPLETED, CANCELLED, REJECTED, EXPIRED
- Payment Statuses: UNPAID, PARTIAL, PAID

### BookingPayment
- Records individual cash payments
- Multiple partial payments supported
- Automatically updates booking payment status

### ClientProfile
- Client information (name, phone, address, ID number, etc.)
- Linked to Django User model

### ProviderProfile
- Provider information (name, company, tax ID, etc.)
- Linked to Django User model

### Property
- Property/listing information
- Fields: name, type, location, bedrooms, bathrooms, monthly price
- Linked to provider

## Architecture

```
homezup/
├── core/                    # Base models and utilities
│   └── models.py           # BaseModel for timestamps
├── users/                   # User management
│   ├── models.py           # ClientProfile, ProviderProfile, Property
│   ├── controllers.py      # API endpoints
│   ├── schemas.py          # Request/response schemas
│   └── admin.py            # Django admin config
├── bookings/               # Booking system
│   ├── models.py           # Booking, BookingPayment
│   ├── services.py         # Business logic
│   ├── selectors.py        # Database queries
│   ├── controllers.py      # API endpoints
│   ├── schemas.py          # Request/response schemas
│   ├── admin.py            # Django admin config
│   └── management/
│       └── commands/       # Management commands
│           ├── update_booking_statuses.py
│           ├── backup_database.py
│           └── seed_data.py
├── homezup/               # Project settings
│   ├── settings.py        # Django configuration
│   ├── urls.py            # URL routing
│   └── wsgi.py            # WSGI application
└── db.sqlite3             # SQLite database
```

## API Examples

### Create Booking
```bash
curl -X POST http://127.0.0.1:8000/api/bookings/ \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "provider_id": 1,
    "property_ref_id": 1,
    "start_date": "2026-10-01",
    "end_date": "2026-12-01",
    "notes": "Monthly rental"
  }'
```

### List Bookings with Filters
```bash
curl "http://127.0.0.1:8000/api/bookings/?status=active&payment_status=unpaid"
```

### Record Payment
```bash
curl -X POST http://127.0.0.1:8000/api/bookings/1/payments \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 5000.00,
    "payment_method": "cash",
    "received_by_user": "Admin",
    "notes": "First payment"
  }'
```

### Get Dashboard
```bash
curl http://127.0.0.1:8000/api/dashboard/
```

### Fitness Classes and Teams

Fitness classes support Boxing, Musculation, Aerobic, and Kick Boxing. The default price is **100.00 MAD (100 DH) per member**. The team total is calculated automatically as `price_per_member x active_members`.

```bash
# List classes and automatic team totals
curl http://127.0.0.1:8000/api/fitness/classes

# Create a class
curl -X POST http://127.0.0.1:8000/api/fitness/classes \
   -H "Content-Type: application/json" \
   -d '{"name":"Evening Boxing","class_type":"boxing","price_per_member":100.00}'

# Add a client to class 1
curl -X POST http://127.0.0.1:8000/api/fitness/classes/1/members \
   -H "Content-Type: application/json" \
   -d '{"client_id":1}'

# Member 360 (gym staff session). Reception, Admin, Super Admin, or is_staff.
# Anonymous 401. Gym member / Trainer group 403. Missing member 404.
# Empty memberships/payments/attendance return [] and reminder is null.
# Attendance is the 50 most recent visits for that member.
curl http://127.0.0.1:8000/api/fitness/members/1/360
```

The Django admin also shows each class's member count and automatic team total in MAD.

## Currency

All monetary values are in **MAD (Moroccan Dirham)**.

## Timezone

The system uses **Africa/Casablanca** timezone (UTC+1).

## Security

- Role-based access control (Admin, Provider, Client)
- Property ownership verification
- Database transactions for critical operations
- CORS enabled for local development
- CSRF protection enabled

## Development

### Running Tests
```bash
python manage.py test
```

### Checking for Issues
```bash
python manage.py check
```

### Database Migrations
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

## Troubleshooting

### Database Locked
If you get a database locked error, ensure no other processes are accessing `db.sqlite3`. Close the admin panel or API requests before running commands.

### Port Already in Use
If port 8000 is already in use:
```bash
python manage.py runserver 8001
```

### Reset Database
To start fresh:
```bash
# Delete db.sqlite3
rm db.sqlite3

# Recreate database
python manage.py migrate

# Seed sample data (optional)
python manage.py seed_data
```

## Support

For issues or questions, refer to the Django documentation at https://docs.djangoproject.com/

## License

This is a local booking management system for Homezup.

---

**Version**: 1.0.0  
**Last Updated**: 2026-09-02
