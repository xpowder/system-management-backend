"""Gym-local dashboard aggregates. Counts only — no member/payment lists."""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Case, Count, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from ninja.errors import HttpError

from fitness.models import Attendance, ClassSchedule, GymPayment, Membership


ZERO = Decimal('0.00')
MONEY = DecimalField(max_digits=12, decimal_places=2)


def parse_dashboard_date(value):
    if value in (None, ''):
        raise HttpError(400, 'date is required (YYYY-MM-DD)')
    try:
        day = datetime.strptime(str(value).strip(), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        raise HttpError(400, 'date must be a valid date (YYYY-MM-DD)')
    today = timezone.localdate()
    if day.year < 2000 or day.year > today.year + 1:
        raise HttpError(400, 'Year is out of range')
    return day


def local_day_bounds(day):
    start = timezone.make_aware(datetime.combine(day, datetime.min.time()), timezone.get_current_timezone())
    return start, start + timedelta(days=1)


def _covering(day):
    return Q(status_override='', start_date__lte=day, end_date__gte=day)


def _paid_total_annotation():
    return Coalesce(
        Sum('payments__amount', filter=Q(payments__status='paid')),
        Value(ZERO),
        output_field=MONEY,
    )


def _remaining_annotation():
    return Case(
        When(price__gt=F('paid_total'), then=F('price') - F('paid_total')),
        default=Value(ZERO),
        output_field=MONEY,
    )


def _attendance_counts(start, end):
    row = Attendance.objects.filter(checked_in_at__gte=start, checked_in_at__lt=end).aggregate(
        checked_in=Count('id'),
        inside=Count('id', filter=Q(checked_out_at__isnull=True)),
    )
    return int(row['checked_in'] or 0), int(row['inside'] or 0)


def _membership_counts(day):
    covering = Membership.objects.filter(member__is_active=True).filter(_covering(day))
    current = covering.aggregate(
        active=Count('member_id', distinct=True),
        expiring_today=Count('member_id', filter=Q(end_date=day), distinct=True),
    )
    covering_members = covering.values('member_id')
    expired = (
        Membership.objects.filter(member__is_active=True, status_override='', end_date__lt=day)
        .exclude(member_id__in=covering_members)
        .aggregate(expired=Count('member_id', distinct=True))
    )
    return (
        int(current['active'] or 0),
        int(expired['expired'] or 0),
        int(current['expiring_today'] or 0),
    )


def _payment_counts(start, end):
    today_total = GymPayment.objects.filter(
        status='paid',
        received_at__gte=start,
        received_at__lt=end,
    ).aggregate(total=Coalesce(Sum('amount'), Value(ZERO), output_field=MONEY))['total']
    money = (
        Membership.objects.exclude(status_override='cancelled')
        .annotate(paid_total=_paid_total_annotation())
        .annotate(remaining=_remaining_annotation())
        .aggregate(
            outstanding_total=Coalesce(Sum('remaining'), Value(ZERO), output_field=MONEY),
            members_with_balance=Count(
                'member_id',
                filter=Q(remaining__gt=0, member__is_active=True),
                distinct=True,
            ),
        )
    )
    return today_total or ZERO, money['outstanding_total'] or ZERO, int(money['members_with_balance'] or 0)


def _class_counts(day):
    row = ClassSchedule.objects.filter(
        is_active=True,
        training_class__is_active=True,
        weekday=day.weekday(),
    ).aggregate(
        today_count=Count('id'),
        trainer_count=Count('trainer_id', distinct=True),
    )
    return int(row['today_count'] or 0), int(row['trainer_count'] or 0)


def build_dashboard_summary(day: date):
    start, end = local_day_bounds(day)
    checked_in, inside = _attendance_counts(start, end)
    active, expired, expiring_today = _membership_counts(day)
    today_total, outstanding_total, members_with_balance = _payment_counts(start, end)
    class_count, trainer_count = _class_counts(day)
    return {
        'date': day,
        'timezone': timezone.get_current_timezone_name(),
        'attendance': {
            'checked_in': checked_in,
            'inside': inside,
        },
        'memberships': {
            'active': active,
            'expired': expired,
            'expiring_today': expiring_today,
        },
        'payments': {
            'today_total': today_total,
            'outstanding_total': outstanding_total,
        },
        'classes': {
            'today_count': class_count,
        },
        'trainers': {
            'today_count': trainer_count,
        },
        'attention': {
            'expiring_today': expiring_today,
            'expired': expired,
            'members_with_balance': members_with_balance,
        },
    }
