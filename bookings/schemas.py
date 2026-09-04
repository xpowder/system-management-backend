from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from ninja import Schema


class BookingOut(Schema):
    id: int
    client_id: int
    provider_id: int
    property_ref_id: int
    start_date: date
    end_date: date
    monthly_price: Decimal
    number_of_months: int
    total_price: Decimal
    status: str
    payment_status: str
    payment_method: str
    total_paid: Decimal
    remaining_balance: Decimal
    notes: str
    approved_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BookingIn(Schema):
    client_id: int
    property_id: Optional[int] = None
    property_ref_id: Optional[int] = None
    provider_id: Optional[int] = None
    start_date: date
    end_date: date
    notes: Optional[str] = ""


class BookingNotesIn(Schema):
    notes: Optional[str] = ""


class BookingApproveIn(BookingNotesIn):
    pass


class BookingRejectIn(BookingNotesIn):
    pass


class BookingCancelIn(BookingNotesIn):
    pass


class BookingPaymentOut(Schema):
    id: int
    booking_id: int
    amount: Decimal
    status: str
    payment_method: str
    received_by_user: str
    received_at: datetime
    receipt_number: Optional[str] = None
    notes: str
    created_at: datetime

    class Config:
        from_attributes = True


class BookingPaymentIn(Schema):
    amount: Decimal
    payment_method: str = "cash"
    received_by_user: Optional[str] = ""
    receipt_number: Optional[str] = None
    notes: Optional[str] = ""


class ErrorOut(Schema):
    error: str


class DashboardOut(Schema):
    today: date
    total_properties: int
    available_properties: int
    occupied_properties: int
    active_bookings: int
    pending_bookings: int
    completed_bookings: int
    today_payments: Decimal
    month_payments: Decimal
    outstanding_balance: Decimal


class MonthlyRevenueOut(Schema):
    year: int
    month: int
    month_label: str
    cash_collected: Decimal
    currency: str = "MAD"


class OutstandingPaymentOut(Schema):
    client_name: str
    booking_id: int
    remaining_balance: Decimal
    due_date: date


class OccupancyOut(Schema):
    total_properties: int
    occupied: int
    available: int
    occupancy_rate: Decimal


class AvailabilityIntervalOut(Schema):
    start_date: date
    end_date: date
    status: str
    booking_id: Optional[int] = None


class AvailabilityOut(Schema):
    property_id: int
    start_date: date
    end_date: date
    available: bool
    intervals: List[AvailabilityIntervalOut]


class ReceiptOut(Schema):
    company: str = "AUMB"
    booking_id: int
    client: str
    property: str
    provider: str
    payment_date: datetime
    amount_paid: Decimal
    payment_method: str
    total_booking_price: Decimal
    total_paid: Decimal
    remaining_balance: Decimal
    received_by: str
    receipt_number: str
    currency: str = "MAD"


class BookingPreviewOut(Schema):
    months: int
    monthly_price: Decimal
    total_price: Decimal
    payment_method: str = "cash"
    currency: str = "MAD"
