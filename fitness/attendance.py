"""Front-desk check-in helpers: card codes, lookup, visits, QR."""
from io import BytesIO
import re

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from ninja.errors import HttpError

from fitness.models import Attendance, ClassMember, Membership, TrainingClass
from users.models import ClientProfile

CHECKIN_STATUSES = {'active', 'expiring_soon'}
CARD_RE = re.compile(r'^(?:FO-?)(\d+)$', re.I)
MEMBER_RE = re.compile(r'^(?:flexoper:member:|member:)(\d+)$', re.I)


def member_card_code(member_id):
    return f'FO-{int(member_id):06d}'


def _digits(value):
    return re.sub(r'\D', '', value or '')


def _member_class(member):
    assignment = ClassMember.objects.filter(client_id=member.id, is_active=True).select_related('training_class').first()
    if not assignment:
        return None, ''
    return assignment.training_class_id, assignment.training_class.name


def _membership_status(member):
    statuses = [item.status for item in Membership.objects.filter(member=member)]
    for wanted in ('active', 'expiring_soon', 'upcoming', 'expired', 'suspended', 'cancelled'):
        if wanted in statuses:
            return wanted
    return 'none'


def can_check_in(member):
    return _membership_status(member) in CHECKIN_STATUSES


def open_visit_today(member_id):
    return Attendance.objects.filter(
        member_id=member_id,
        checked_in_at__date=timezone.localdate(),
        checked_out_at__isnull=True,
    ).select_related('member__user').first()


def attendance_data(visit, class_id=None, class_name=None):
    member = visit.member
    if class_id is None and class_name is None:
        class_id, class_name = _member_class(member)
    return {
        'id': visit.id,
        'member_id': visit.member_id,
        'member_name': f'{member.user.first_name} {member.user.last_name}'.strip() or member.user.username,
        'phone': member.phone or '',
        'card_code': member_card_code(visit.member_id),
        'class_id': class_id,
        'class_name': class_name or '',
        'checked_in_at': visit.checked_in_at,
        'checked_out_at': visit.checked_out_at,
        'is_inside': visit.checked_out_at is None,
    }


def desk_member(member):
    class_id, class_name = _member_class(member)
    visit = open_visit_today(member.id)
    status = _membership_status(member)
    return {
        'id': member.id,
        'name': f'{member.user.first_name} {member.user.last_name}'.strip() or member.user.username,
        'phone': member.phone or '',
        'card_code': member_card_code(member.id),
        'id_number': member.id_number or '',
        'class_id': class_id,
        'class_name': class_name,
        'membership_status': status,
        'can_check_in': status in CHECKIN_STATUSES,
        'is_inside': bool(visit),
        'visit_id': visit.id if visit else None,
        'checked_in_at': visit.checked_in_at if visit else None,
    }


def _exact_member(query):
    raw = (query or '').strip()
    if not raw:
        return None
    compact = raw.replace(' ', '')
    match = CARD_RE.match(compact) or MEMBER_RE.match(compact)
    if match:
        return ClientProfile.objects.filter(id=int(match.group(1)), is_active=True).select_related('user').first()
    by_number = ClientProfile.objects.filter(is_active=True, id_number__iexact=raw).select_related('user').first()
    if by_number:
        return by_number
    if raw.isdigit():
        return ClientProfile.objects.filter(id=int(raw), is_active=True).select_related('user').first()
    digits = _digits(raw)
    if len(digits) >= 8:
        for member in ClientProfile.objects.filter(is_active=True).exclude(phone='').select_related('user'):
            phone = _digits(member.phone)
            if phone == digits or phone.endswith(digits) or digits.endswith(phone):
                return member
    return None


def lookup_members(query, limit=8):
    raw = (query or '').strip()
    exact = _exact_member(raw)
    if exact:
        return True, [exact]
    if len(raw) < 2:
        return False, []
    digits = _digits(raw)
    filters = (
        Q(user__first_name__icontains=raw)
        | Q(user__last_name__icontains=raw)
        | Q(phone__icontains=raw)
        | Q(id_number__icontains=raw)
    )
    if len(digits) >= 4:
        filters |= Q(phone__icontains=digits)
    members = list(
        ClientProfile.objects.filter(is_active=True).filter(filters).select_related('user')[:limit]
    )
    return False, members


def list_today_visits():
    visits = list(
        Attendance.objects.filter(checked_in_at__date=timezone.localdate())
        .select_related('member__user')
        .order_by('-checked_in_at')[:500]
    )
    member_ids = [item.member_id for item in visits]
    classes = {
        row.client_id: row.training_class
        for row in ClassMember.objects.filter(is_active=True, client_id__in=member_ids).select_related('training_class')
    }
    rows = []
    for visit in visits:
        training_class = classes.get(visit.member_id)
        rows.append(attendance_data(
            visit,
            training_class.id if training_class else None,
            training_class.name if training_class else '',
        ))
    return rows


def class_headcount(visits):
    buckets = {}
    for training_class in TrainingClass.objects.filter(is_active=True):
        buckets[training_class.id] = {
            'class_id': training_class.id,
            'class_name': training_class.name,
            'checkins': 0,
            'inside': 0,
        }
    unassigned = {'class_id': None, 'class_name': 'No class', 'checkins': 0, 'inside': 0}
    for visit in visits:
        class_id = visit.get('class_id')
        if not class_id:
            bucket = unassigned
        else:
            bucket = buckets.get(class_id)
            if bucket is None:
                bucket = {
                    'class_id': class_id,
                    'class_name': visit.get('class_name') or 'Unknown class',
                    'checkins': 0,
                    'inside': 0,
                }
                buckets[class_id] = bucket
        bucket['checkins'] += 1
        if visit.get('is_inside'):
            bucket['inside'] += 1
    rows = list(buckets.values())
    if unassigned['checkins']:
        rows.append(unassigned)
    rows.sort(key=lambda item: (-item['inside'], -item['checkins'], item['class_name'].lower()))
    return rows


def require_checkin_member(member_id):
    try:
        member = ClientProfile.objects.select_related('user').get(id=member_id, is_active=True)
    except ClientProfile.DoesNotExist:
        raise HttpError(404, 'Member not found')
    if not can_check_in(member):
        raise HttpError(400, 'Member does not have an active membership')
    return member


def qr_response(member_id):
    try:
        member = ClientProfile.objects.get(id=member_id, is_active=True)
    except ClientProfile.DoesNotExist:
        raise HttpError(404, 'Member not found')
    try:
        import segno
    except ImportError:
        raise HttpError(503, 'QR codes are not available on this server')
    qr = segno.make(member_card_code(member.id), error='m')
    buffer = BytesIO()
    qr.save(buffer, kind='svg', scale=5, border=1)
    return HttpResponse(buffer.getvalue(), content_type='image/svg+xml')
