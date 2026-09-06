"""Weekly class-schedule expansion for the gym calendar."""
from datetime import date, datetime, timedelta

from django.utils import timezone
from ninja.errors import HttpError


CALENDAR_MAX_DAYS = 62

WEEKDAY_NAME_TO_INT = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6,
}
WEEKDAY_INT_TO_NAME = {value: key for key, value in WEEKDAY_NAME_TO_INT.items()}


def parse_weekday(value):
    raw = (value or '').strip().lower()
    if raw not in WEEKDAY_NAME_TO_INT:
        raise HttpError(
            400,
            'weekday must be monday, tuesday, wednesday, thursday, friday, saturday, or sunday',
        )
    return WEEKDAY_NAME_TO_INT[raw]


def weekday_name(value):
    try:
        return WEEKDAY_INT_TO_NAME[int(value)]
    except (KeyError, TypeError, ValueError):
        raise HttpError(
            400,
            'weekday must be monday, tuesday, wednesday, thursday, friday, saturday, or sunday',
        )


def parse_calendar_bounds(from_value, to_value):
    if from_value in (None, '') or to_value in (None, ''):
        raise HttpError(400, 'from and to dates are required (YYYY-MM-DD)')
    start = _parse_iso_date(from_value, 'from')
    end = _parse_iso_date(to_value, 'to')
    if start > end:
        raise HttpError(400, 'from must be on or before to')
    span = (end - start).days + 1
    if span > CALENDAR_MAX_DAYS:
        raise HttpError(400, f'Date range cannot exceed {CALENDAR_MAX_DAYS} days')
    return start, end


def _parse_iso_date(value, field):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip(), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        raise HttpError(400, f'{field} must be a valid date (YYYY-MM-DD)')


def weekdays_in_range(start, end):
    if (end - start).days >= 6:
        return None
    values = set()
    current = start
    while current <= end:
        values.add(current.weekday())
        current += timedelta(days=1)
    return values


def occurrence_dates(start, end, weekday):
    offset = (weekday - start.weekday()) % 7
    current = start + timedelta(days=offset)
    while current <= end:
        yield current
        current += timedelta(days=7)


def combine_local(day, clock):
    return timezone.make_aware(datetime.combine(day, clock), timezone.get_current_timezone())


def calendar_items(schedules, start, end):
    items = []
    for schedule in schedules:
        roster = getattr(schedule, 'roster_count', None)
        if roster is None:
            roster = schedule.training_class.member_count
        trainer = schedule.trainer
        for day in occurrence_dates(start, end, schedule.weekday):
            items.append({
                'schedule_id': schedule.id,
                'training_class_id': schedule.training_class_id,
                'class_name': schedule.training_class.name,
                'class_type': schedule.training_class.class_type,
                'date': day,
                'weekday': weekday_name(schedule.weekday),
                'start_time': schedule.start_time,
                'end_time': schedule.end_time,
                'starts_at': combine_local(day, schedule.start_time),
                'ends_at': combine_local(day, schedule.end_time),
                'trainer_id': trainer.id if trainer else None,
                'trainer_name': trainer.name if trainer else None,
                'location': schedule.location or '',
                'capacity': schedule.capacity,
                'member_count': int(roster),
                'is_active': True,
            })
    items.sort(key=lambda item: (
        item['date'],
        item['start_time'],
        item['class_name'].lower(),
        item['schedule_id'],
    ))
    return items
