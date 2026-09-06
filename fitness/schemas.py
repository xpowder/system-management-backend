from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class TrainingClassIn(BaseModel):
    name: str
    class_type: str
    price_per_member: Decimal = Field(default=Decimal('100.00'), ge=0)
    is_active: bool = True


class TrainingClassOut(BaseModel):
    id: int
    name: str
    class_type: str
    price_per_member: Decimal
    member_count: int
    team_total: Decimal
    is_active: bool

    class Config:
        from_attributes = True


class ClassScheduleIn(BaseModel):
    training_class_id: int
    weekday: str
    start_time: time
    end_time: time
    trainer_id: Optional[int] = None
    location: str = ''
    capacity: Optional[int] = Field(default=None, ge=1)
    is_active: bool = True


class ClassScheduleOut(BaseModel):
    id: int
    training_class_id: int
    class_name: str
    class_type: str
    weekday: str
    start_time: time
    end_time: time
    trainer_id: Optional[int] = None
    trainer_name: Optional[str] = None
    location: str = ''
    capacity: Optional[int] = None
    is_active: bool


class CalendarOccurrenceOut(BaseModel):
    schedule_id: int
    training_class_id: int
    class_name: str
    class_type: str
    date: date
    weekday: str
    start_time: time
    end_time: time
    starts_at: datetime
    ends_at: datetime
    trainer_id: Optional[int] = None
    trainer_name: Optional[str] = None
    location: str = ''
    capacity: Optional[int] = None
    member_count: int
    is_active: bool


class ClassCalendarOut(BaseModel):
    start_date: date
    end_date: date
    timezone: str
    items: List[CalendarOccurrenceOut]


class ClassRevenueOut(BaseModel):
    id: Optional[int] = None
    name: str
    class_type: str
    class_type_label: str
    member_count: int
    price_per_member: Decimal
    expected_monthly: Decimal
    collected: Decimal
    outstanding: Decimal


class ClassRevenueReportOut(BaseModel):
    year: int
    month: int
    label: str
    total_expected: Decimal
    total_collected: Decimal
    total_outstanding: Decimal
    collection_rate: Decimal
    classes: List[ClassRevenueOut]


class TrainerIn(BaseModel):
    first_name: str
    last_name: str
    specialization: str = ''
    phone: str = ''
    monthly_pay: Decimal = Field(default=Decimal('0.00'), ge=0)
    pay_amount: Optional[Decimal] = Field(default=None, ge=0)
    is_paid: bool = False
    is_active: bool = True


class TrainerPayrollIn(BaseModel):
    year: Optional[int] = None
    month: Optional[int] = None
    pay_amount: Optional[Decimal] = Field(default=None, ge=0)
    is_paid: Optional[bool] = None
    notes: str = ''


class TrainerOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    specialization: str
    phone: str
    is_active: bool
    monthly_pay: Decimal
    pay_amount: Decimal
    is_paid: bool
    year: int
    month: int


class TrainerPayrollRowOut(BaseModel):
    id: int
    name: str
    specialization: str
    monthly_pay: Decimal
    pay_amount: Decimal
    is_paid: bool


class TrainerPayrollReportOut(BaseModel):
    year: int
    month: int
    label: str
    total_due: Decimal
    total_paid: Decimal
    total_unpaid: Decimal
    paid_count: int
    unpaid_count: int
    trainers: List[TrainerPayrollRowOut]


class GymExpenseIn(BaseModel):
    category: str
    title: str = ''
    amount: Decimal = Field(gt=0)
    year: Optional[int] = None
    month: Optional[int] = None
    notes: str = ''


class GymExpenseOut(BaseModel):
    id: int
    category: str
    category_label: str
    title: str
    amount: Decimal
    year: int
    month: int
    notes: str


class ExpenseCategoryTotalOut(BaseModel):
    category: str
    category_label: str
    total: Decimal
    count: int


class MonthlyOverviewOut(BaseModel):
    year: int
    month: int
    label: str
    collected: Decimal
    expected: Decimal
    outstanding: Decimal
    operating_total: Decimal
    trainer_due: Decimal
    trainer_paid: Decimal
    total_spend: Decimal
    net: Decimal
    categories: List[ExpenseCategoryTotalOut]
    expenses: List[GymExpenseOut]


class ClassMemberIn(BaseModel):
    client_id: int


class MemberClassIn(BaseModel):
    class_id: Optional[int] = None


class MemberClassOut(BaseModel):
    id: Optional[int] = None
    training_class_id: Optional[int] = None
    client_id: int


class ClassMemberOut(BaseModel):
    id: int
    training_class_id: int
    client_id: int
    joined_at: date
    is_active: bool

    class Config:
        from_attributes = True


class MemberIn(BaseModel):
    first_name: str
    last_name: str
    phone: str = ''
    email: str = ''
    id_number: str = ''
    address: str = ''
    city: str = ''
    country: str = 'Morocco'
    postal_code: str = ''


class MemberOut(BaseModel):
    id: int
    name: str
    phone: str
    email: str
    id_number: str = ''
    address: str = ''
    city: str = ''
    country: str = 'Morocco'
    postal_code: str = ''
    card_code: str = ''
    class_id: Optional[int] = None
    class_name: str = ''


class Member360ClassOut(BaseModel):
    id: int
    name: str


class Member360PlanOut(BaseModel):
    id: int
    name: str
    duration_months: int
    price: Decimal


class Member360MemberOut(MemberOut):
    is_active: bool = True


class Member360MembershipOut(BaseModel):
    id: int
    member_id: int
    plan_id: int
    plan: Member360PlanOut
    start_date: date
    end_date: date
    price: Decimal
    status: str
    payment_status: str
    total_paid: Decimal
    remaining_balance: Decimal
    notes: str = ''


class AttendanceIn(BaseModel):
    member_id: int


class AttendanceCheckOutIn(BaseModel):
    member_id: Optional[int] = None
    visit_id: Optional[int] = None


class AttendanceOut(BaseModel):
    id: int
    member_id: int
    member_name: str = ''
    phone: str = ''
    card_code: str = ''
    class_id: Optional[int] = None
    class_name: str = ''
    checked_in_at: datetime
    checked_out_at: Optional[datetime] = None
    is_inside: bool = False


class AttendanceDeskMemberOut(BaseModel):
    id: int
    name: str
    phone: str = ''
    card_code: str
    id_number: str = ''
    class_id: Optional[int] = None
    class_name: str = ''
    membership_status: str = 'none'
    can_check_in: bool = False
    is_inside: bool = False
    visit_id: Optional[int] = None
    checked_in_at: Optional[datetime] = None


class AttendanceClassCountOut(BaseModel):
    class_id: Optional[int] = None
    class_name: str
    checkins: int
    inside: int


class AttendanceLookupOut(BaseModel):
    query: str
    exact: bool = False
    matches: List[AttendanceDeskMemberOut]


class AttendanceDeskOut(BaseModel):
    date: date
    checkins: int
    inside: int
    checkouts: int
    by_class: List[AttendanceClassCountOut]
    visits: List[AttendanceOut]


class PlanIn(BaseModel):
    name: str
    duration_months: int = Field(ge=1)
    price: Decimal = Field(ge=0)
    description: str = ''
    is_active: bool = True


class PlanOut(PlanIn):
    id: int
    member_count: int = 0

    class Config:
        from_attributes = True


class MembershipIn(BaseModel):
    member_id: int
    plan_id: int
    start_date: date
    notes: str = ''
    price: Optional[Decimal] = None


class MembershipOut(BaseModel):
    id: int
    member_id: int
    plan_id: int
    start_date: date
    end_date: date
    price: Decimal
    status: str
    payment_status: str
    total_paid: Decimal
    remaining_balance: Decimal
    notes: str = ''

class PaymentStatusUpdateIn(BaseModel):
    status: str


class MembershipPriceIn(BaseModel):
    price: Decimal = Field(ge=0)


class GymPaymentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    received_by: str
    notes: str = ''
    remaining: Optional[Decimal] = Field(default=None, ge=0)


class MembershipRemainingIn(BaseModel):
    remaining: Decimal = Field(ge=0)


class GymPaymentOut(BaseModel):
    id: int
    membership_id: int
    member_id: Optional[int] = None
    member_name: str = ''
    id_number: str = ''
    amount: Decimal
    payment_method: str
    received_by: str
    received_at: datetime
    notes: str = ''
    remaining_balance: Optional[Decimal] = None
    receipt_number: str = ''

    class Config:
        from_attributes = True


class NotificationSettingsIn(BaseModel):
    membership_expiring_soon: bool = True
    membership_expired: bool = True
    outstanding_payment: bool = True
    new_member_registered: bool = True
    payment_received: bool = True
    important_system_alerts: bool = True
    new_membership_created: bool = True
    membership_renewed: bool = True
    partial_payment: bool = True
    member_updated: bool = True
    member_deactivated: bool = True
    member_check_in: bool = True
    new_staff_user_created: bool = True
    user_role_changed: bool = True
    user_deactivated: bool = True


class NotificationSettingsOut(NotificationSettingsIn):
    id: int

    class Config:
        from_attributes = True


class NotificationOut(BaseModel):
    id: int
    category: str
    title: str
    message: str
    is_read: bool
    member_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WhatsAppReminderOut(BaseModel):
    membership_id: int
    member_id: int
    member_name: str
    phone: str
    whatsapp_url: Optional[str] = None
    status: str
    payment_status: str
    end_date: date
    days_left: int
    remaining: Decimal
    reasons: List[str]
    message: str
    last_sent_at: Optional[datetime] = None
    reminded_today: bool = False


class WhatsAppReminderListOut(BaseModel):
    expiring: int
    expired: int
    unpaid: int
    missing_phone: int
    items: List[WhatsAppReminderOut]


class WhatsAppReminderSentIn(BaseModel):
    message: str = ''


class Member360Out(BaseModel):
    """Nested desk view for one member. Attendance is the 50 most recent visits."""
    member: Member360MemberOut
    training_class: Optional[Member360ClassOut] = None
    memberships: List[Member360MembershipOut]
    payments: List[GymPaymentOut]
    attendance: List[AttendanceOut]
    reminder: Optional[WhatsAppReminderOut] = None
