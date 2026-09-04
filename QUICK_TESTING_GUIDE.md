# Quick Testing Guide

This guide helps you test the Homezup booking system APIs immediately after setup.

## Prerequisites

1. Server running: `python manage.py runserver`
2. Sample data loaded: `python manage.py seed_data` (already done)
3. Admin user created: username `admin`, password `admin123`

---

## Test Sequence

Follow this sequence to test all major features:

### Step 1: Test Server Connection

```bash
curl http://127.0.0.1:8000/api/
```

**Expected Response**: API welcome message with endpoints list

---

### Step 2: Test Dashboard

```bash
curl http://127.0.0.1:8000/api/dashboard/
```

**Expected Response**:
```json
{
  "total_properties": 3,
  "available_properties": 0,
  "occupied_properties": 3,
  "active_bookings": 3,
  "pending_bookings": 0,
  "today_payments": "0.00",
  "month_payments": "0.00",
  "outstanding_balance": "30000.00"
}
```

---

### Step 3: Test Client Endpoints

#### List Clients
```bash
curl http://127.0.0.1:8000/api/clients/
```

**Expected Response**: Array of 3 sample clients

#### Get Specific Client
```bash
curl http://127.0.0.1:8000/api/clients/1/
```

#### Search Clients
```bash
curl "http://127.0.0.1:8000/api/clients/?search=Ahmed"
```

---

### Step 4: Test Provider Endpoints

#### List Providers
```bash
curl http://127.0.0.1:8000/api/providers/
```

**Expected Response**: Array of 2 sample providers

#### Get Specific Provider
```bash
curl http://127.0.0.1:8000/api/providers/1/
```

---

### Step 5: Test Property Endpoints

#### List Properties
```bash
curl http://127.0.0.1:8000/api/properties/
```

**Expected Response**: Array of 3 sample properties

#### Get Specific Property
```bash
curl http://127.0.0.1:8000/api/properties/1/
```

#### Check Property Availability
```bash
curl "http://127.0.0.1:8000/api/properties/1/availability?start_date=2026-12-10&end_date=2027-01-10"
```

**Expected Response**:
```json
{
  "available": true
}
```

---

### Step 6: Test Booking Endpoints

#### List All Bookings
```bash
curl http://127.0.0.1:8000/api/bookings/
```

**Expected Response**: Array of 3 sample bookings

#### Get Specific Booking
```bash
curl http://127.0.0.1:8000/api/bookings/1/
```

#### Filter Bookings by Status
```bash
curl "http://127.0.0.1:8000/api/bookings/?status=active"
```

#### Search Bookings
```bash
curl "http://127.0.0.1:8000/api/bookings/?search=Ahmed"
```

---

### Step 7: Test Payment Endpoints

#### View Payment History
```bash
curl http://127.0.0.1:8000/api/bookings/1/payments/
```

**Expected Response**: Empty array (no payments recorded yet)

#### Record a Payment
```bash
curl -X POST http://127.0.0.1:8000/api/bookings/1/payments \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 5000.00,
    "payment_method": "cash",
    "received_by_user": "Tester",
    "receipt_number": "REC-TEST-001",
    "notes": "Test payment"
  }'
```

**Expected Response**:
```json
{
  "id": 1,
  "booking_id": 1,
  "amount": "5000.00",
  "status": "paid",
  "payment_method": "cash",
  "received_by_user": "Tester",
  "received_at": "2026-09-02T...",
  "receipt_number": "REC-TEST-001",
  "notes": "Test payment"
}
```

#### View Updated Payment History
```bash
curl http://127.0.0.1:8000/api/bookings/1/payments/
```

**Expected Response**: 1 payment in the list

---

### Step 8: Test Booking Status Transitions

#### Get Current Booking Status
```bash
curl http://127.0.0.1:8000/api/bookings/2/
```

Note the status field

#### Approve Booking (if status is PENDING)
```bash
curl -X POST http://127.0.0.1:8000/api/bookings/2/approve \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Approved by test"
  }'
```

#### View Updated Status
```bash
curl http://127.0.0.1:8000/api/bookings/2/
```

---

### Step 9: Test Reports

#### Outstanding Payments Report
```bash
curl http://127.0.0.1:8000/api/reports/outstanding/
```

**Expected Response**: List of unpaid bookings with client names and amounts

#### Occupancy Report
```bash
curl http://127.0.0.1:8000/api/reports/occupancy/
```

**Expected Response**:
```json
{
  "total_properties": 3,
  "occupied": 3,
  "available": 0,
  "occupancy_rate": "100.00"
}
```

---

### Step 10: Test Calculation Helper

```bash
curl "http://127.0.0.1:8000/api/bookings/1/calculate?start_date=2026-10-15&end_date=2026-12-15"
```

**Expected Response**:
```json
{
  "months": 2,
  "monthly_price": "5000.00",
  "total_price": "10000.00"
}
```

---

## Data Modification Tests

### Create a New Client

```bash
curl -X POST http://127.0.0.1:8000/api/clients/ \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Test",
    "last_name": "Client",
    "email": "test@example.com",
    "phone": "0612345678",
    "address": "123 Test St",
    "city": "Marrakech",
    "postal_code": "40000",
    "id_number": "AB999999"
  }'
```

**Expected Response**: New client created with ID 4

### Create a New Property

First, get a provider ID from the providers list (should be 1 or 2).

```bash
curl -X POST "http://127.0.0.1:8000/api/properties/?provider_id=1&name=Test%20Property&description=Test%20Description&property_type=house&address=456%20Test%20Blvd&city=Fez&postal_code=30000&monthly_price=4500&bedrooms=2&bathrooms=1"
```

**Expected Response**: New property created

### Create a New Booking

```bash
curl -X POST http://127.0.0.1:8000/api/bookings/ \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 4,
    "provider_id": 1,
    "property_ref_id": 4,
    "start_date": "2026-10-01",
    "end_date": "2026-11-01",
    "notes": "Test booking creation"
  }'
```

**Expected Response**: New booking created with PENDING status and UNPAID payment status

---

## Error Testing

### Test Invalid Dates

```bash
curl -X POST http://127.0.0.1:8000/api/bookings/ \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "provider_id": 1,
    "property_ref_id": 1,
    "start_date": "2026-12-01",
    "end_date": "2026-10-01",
    "notes": "Invalid dates"
  }'
```

**Expected Response**: Error message about invalid date range

### Test Overlapping Dates

```bash
curl -X POST http://127.0.0.1:8000/api/bookings/ \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 2,
    "provider_id": 1,
    "property_ref_id": 1,
    "start_date": "2026-10-15",
    "end_date": "2026-11-15",
    "notes": "Overlaps with existing booking"
  }'
```

**Expected Response**: Error message about property unavailability

### Test Over-Payment

```bash
curl -X POST http://127.0.0.1:8000/api/bookings/1/payments \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 50000.00,
    "payment_method": "cash",
    "received_by_user": "Tester",
    "receipt_number": "REC-TEST-999"
  }'
```

**Expected Response**: Error message about amount exceeding remaining balance

---

## Admin Interface Testing

### Access Admin Panel
1. Open browser: http://127.0.0.1:8000/admin
2. Login with: username `admin`, password `admin123`

### Admin Features to Test
1. **Clients**
   - View 3 sample clients
   - Search by name or phone
   - Edit client information
   - Add new client
   - View client bookings

2. **Providers**
   - View 2 sample providers
   - Search by company name
   - Edit provider information
   - View provider properties

3. **Properties**
   - View 3 sample properties
   - Search by name or city
   - Edit property details
   - Toggle active/inactive status

4. **Bookings**
   - View 3 sample bookings
   - Filter by status (active, pending)
   - Filter by payment status
   - View booking details
   - Edit booking notes
   - View client information

5. **Payments**
   - View payment history
   - Search by receipt number
   - View payment details
   - Sort by date

---

## Performance Testing

### List Large Dataset (Pagination)
```bash
curl "http://127.0.0.1:8000/api/bookings/?limit=50&offset=0"
```

### Search Performance
```bash
curl "http://127.0.0.1:8000/api/bookings/?search=Hassan&limit=10"
```

### Filter Combinations
```bash
curl "http://127.0.0.1:8000/api/bookings/?status=active&payment_status=unpaid&client_id=1"
```

---

## Database Testing

### Run Tests
```bash
python manage.py test bookings
```

**Expected Output**:
```
Found 25 test(s).
Creating test database...
System check identified no issues (0 silenced).
.........................
Ran 25 tests in 0.152s
OK
```

### Backup Database
```bash
python manage.py backup_database
```

**Check backups/**: Should contain `db_YYYY-MM-DD_HH-MM-SS.sqlite3`

### View Database via Admin
```bash
# All data is accessible and editable in the admin panel
http://127.0.0.1:8000/admin
```

---

## Common Issues & Solutions

### Port 8000 Already in Use
```bash
python manage.py runserver 8001
# Then access at http://127.0.0.1:8001
```

### Sample Data Not Loading
```bash
python manage.py migrate
python manage.py seed_data
```

### Getting "Page Not Found" Error
- Ensure server is running
- Check URL spelling (case-sensitive)
- Make sure venv is activated

### Database Locked Error
- Close all terminals
- Wait 5 seconds
- Restart server

### Reset Everything
```bash
rm db.sqlite3
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

---

## Testing Checklist

- [ ] Server starts without errors
- [ ] Dashboard loads with data
- [ ] Can list clients, providers, properties
- [ ] Can view specific booking details
- [ ] Can record payments
- [ ] Can transition booking status (approve/reject)
- [ ] Outstanding payments report works
- [ ] Occupancy report works
- [ ] Admin panel accessible with correct credentials
- [ ] Can edit data in admin panel
- [ ] Tests all pass (25/25)
- [ ] Calculations correct (months, price)
- [ ] Date validation works
- [ ] Search and filters work
- [ ] Can create new bookings
- [ ] Payment status updates after recording payment

---

## Next Steps

After confirming all tests pass:

1. Review sample data in admin panel
2. Test your own custom booking scenario
3. Export data for backup
4. Plan frontend development (if needed)
5. Configure for production (if deploying)
6. Set up automated backups
7. Configure daily status update command

---

## Support

Refer to:
- `README.md` - Installation guide
- `API_GUIDE.md` - Complete API reference
- `IMPLEMENTATION_SUMMARY.md` - Architecture overview
