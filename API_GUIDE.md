# API Usage Guide

## Base URL

```
http://127.0.0.1:8000/api
```

## Authentication

The system uses Django's built-in authentication. For now, API calls don't require authentication headers for demonstration purposes. In production, implement token-based authentication.

## Common Response Format

### Success Response
```json
{
  "id": 1,
  "status": "success",
  "data": { ... }
}
```

### Error Response
```json
{
  "error": "Error message describing what went wrong"
}
```

## Booking Endpoints

### Create Booking
**POST** `/api/bookings/`

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

**Response**
```json
{
  "id": 1,
  "client_id": 1,
  "provider_id": 1,
  "property_ref_id": 1,
  "start_date": "2026-10-01",
  "end_date": "2026-12-01",
  "monthly_price": "5000.00",
  "number_of_months": 2,
  "total_price": "10000.00",
  "status": "pending",
  "payment_status": "unpaid",
  "payment_method": "cash",
  "total_paid": "0.00",
  "remaining_balance": "10000.00",
  "notes": "Monthly rental",
  "created_at": "2026-09-02T10:30:00Z",
  "updated_at": "2026-09-02T10:30:00Z"
}
```

### List Bookings
**GET** `/api/bookings/`

Query Parameters:
- `status` - Filter by status (pending, approved, active, completed, cancelled, rejected)
- `payment_status` - Filter by payment status (unpaid, partial, paid)
- `client_id` - Filter by client
- `property_id` - Filter by property
- `search` - Search by client name or booking ID
- `limit` - Number of results (default: 50, max: 500)
- `offset` - Pagination offset (default: 0)

```bash
curl "http://127.0.0.1:8000/api/bookings/?status=active&payment_status=unpaid&limit=10"
```

### Get Booking Details
**GET** `/api/bookings/{booking_id}/`

```bash
curl http://127.0.0.1:8000/api/bookings/1/
```

### Update Booking
**PATCH** `/api/bookings/{booking_id}/`

```bash
curl -X PATCH http://127.0.0.1:8000/api/bookings/1/ \
  -H "Content-Type: application/json" \
  -d '{
    "status": "approved",
    "notes": "Updated notes"
  }'
```

### Approve Booking
**POST** `/api/bookings/{booking_id}/approve`

```bash
curl -X POST http://127.0.0.1:8000/api/bookings/1/approve \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Approved by manager"
  }'
```

### Reject Booking
**POST** `/api/bookings/{booking_id}/reject`

```bash
curl -X POST http://127.0.0.1:8000/api/bookings/1/reject \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Rejected - property unavailable"
  }'
```

### Cancel Booking
**POST** `/api/bookings/{booking_id}/cancel`

```bash
curl -X POST http://127.0.0.1:8000/api/bookings/1/cancel \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Cancelled by client"
  }'
```

## Payment Endpoints

### Get Payment History
**GET** `/api/bookings/{booking_id}/payments/`

```bash
curl http://127.0.0.1:8000/api/bookings/1/payments/
```

**Response**
```json
[
  {
    "id": 1,
    "booking_id": 1,
    "amount": "5000.00",
    "status": "paid",
    "payment_method": "cash",
    "received_by_user": "Admin",
    "received_at": "2026-09-02T10:35:00Z",
    "receipt_number": "REC001",
    "notes": "First payment",
    "created_at": "2026-09-02T10:35:00Z"
  }
]
```

### Record Cash Payment
**POST** `/api/bookings/{booking_id}/payments`

```bash
curl -X POST http://127.0.0.1:8000/api/bookings/1/payments \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 5000.00,
    "payment_method": "cash",
    "received_by_user": "Admin",
    "receipt_number": "REC001",
    "notes": "First payment"
  }'
```

## Client Endpoints

### Create Client
**POST** `/api/clients/`

```bash
curl -X POST http://127.0.0.1:8000/api/clients/ \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Ahmed",
    "last_name": "Hassan",
    "email": "ahmed@example.com",
    "phone": "0612345678",
    "address": "123 Main St",
    "city": "Casablanca",
    "postal_code": "20000",
    "id_number": "AB123456"
  }'
```

### List Clients
**GET** `/api/clients/`

Query Parameters:
- `search` - Search by name or phone
- `limit` - Number of results (default: 50)
- `offset` - Pagination offset

```bash
curl "http://127.0.0.1:8000/api/clients/?search=Ahmed&limit=10"
```

### Get Client Details
**GET** `/api/clients/{client_id}/`

```bash
curl http://127.0.0.1:8000/api/clients/1/
```

### Update Client
**PATCH** `/api/clients/{client_id}/`

```bash
curl -X PATCH http://127.0.0.1:8000/api/clients/1/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "0687654321",
    "city": "Rabat"
  }'
```

## Provider Endpoints

### Create Provider
**POST** `/api/providers/`

```bash
curl -X POST http://127.0.0.1:8000/api/providers/ \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Provider",
    "email": "john@provider.com",
    "phone": "0612111111",
    "company_name": "Elite Properties",
    "tax_id": "TAX123456"
  }'
```

### List Providers
**GET** `/api/providers/`

```bash
curl http://127.0.0.1:8000/api/providers/
```

### Get Provider Details
**GET** `/api/providers/{provider_id}/`

```bash
curl http://127.0.0.1:8000/api/providers/1/
```

## Property Endpoints

### Create Property
**POST** `/api/properties/`

```bash
curl -X POST "http://127.0.0.1:8000/api/properties/?provider_id=1&name=Apartment%20A1&description=Nice%20apartment&property_type=apartment&address=123%20Test%20St&city=Casablanca&postal_code=20000&monthly_price=5000&bedrooms=3&bathrooms=2"
```

### List Properties
**GET** `/api/properties/`

Query Parameters:
- `provider_id` - Filter by provider
- `search` - Search by name or city
- `limit` - Number of results
- `offset` - Pagination offset

```bash
curl "http://127.0.0.1:8000/api/properties/?search=apartment&limit=10"
```

### Get Property Details
**GET** `/api/properties/{property_id}/`

```bash
curl http://127.0.0.1:8000/api/properties/1/
```

### Check Property Availability
**GET** `/api/properties/{property_id}/availability?start_date=2026-10-01&end_date=2026-12-01`

```bash
curl "http://127.0.0.1:8000/api/properties/1/availability?start_date=2026-10-01&end_date=2026-12-01"
```

**Response**
```json
{
  "available": true
}
```

## Dashboard Endpoint

### Get Dashboard Statistics
**GET** `/api/dashboard/`

```bash
curl http://127.0.0.1:8000/api/dashboard/
```

**Response**
```json
{
  "total_properties": 120,
  "available_properties": 78,
  "occupied_properties": 42,
  "active_bookings": 42,
  "pending_bookings": 6,
  "today_payments": "12500.00",
  "month_payments": "185000.00",
  "outstanding_balance": "45000.00"
}
```

## Reports Endpoints

### Outstanding Payments Report
**GET** `/api/reports/outstanding/`

```bash
curl http://127.0.0.1:8000/api/reports/outstanding/
```

**Response**
```json
[
  {
    "client_name": "Ahmed Hassan",
    "booking_id": 1,
    "remaining_balance": "5000.00",
    "due_date": "2026-12-01"
  }
]
```

### Occupancy Report
**GET** `/api/reports/occupancy/`

```bash
curl http://127.0.0.1:8000/api/reports/occupancy/
```

**Response**
```json
{
  "total_properties": 120,
  "occupied": 42,
  "available": 78,
  "occupancy_rate": "35.00"
}
```

## Booking Calculation Helper

### Calculate Booking Preview
**GET** `/api/bookings/{booking_id}/calculate?start_date=2026-10-01&end_date=2026-12-01`

```bash
curl "http://127.0.0.1:8000/api/bookings/1/calculate?start_date=2026-10-01&end_date=2026-12-01"
```

**Response**
```json
{
  "months": 2,
  "monthly_price": "5000.00",
  "total_price": "10000.00"
}
```

## Admin Interface

Access the Django admin panel at `http://127.0.0.1:8000/admin` with your superuser credentials.

Features:
- Manage clients, providers, and properties
- View and edit bookings
- Track payments
- View booking history and statistics
- Advanced filtering and search

## Error Handling

All error responses follow this format:

```json
{
  "error": "Description of the error"
}
```

Common HTTP Status Codes:
- **200** - OK (successful request)
- **400** - Bad Request (validation error)
- **404** - Not Found (resource doesn't exist)
- **500** - Internal Server Error

## Rate Limiting

No rate limiting is implemented for local development. In production, consider implementing rate limiting to prevent abuse.

## Notes

- All prices are in MAD (Moroccan Dirham)
- All dates are in YYYY-MM-DD format
- All timestamps are in ISO 8601 format with UTC timezone
- Decimal fields preserve up to 2 decimal places for currency
