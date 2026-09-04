from datetime import timedelta
from decimal import Decimal
from calendar import month_name
from typing import List, Optional
from urllib.parse import quote
import re

from ninja import Router
from ninja.errors import HttpError

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Count, DecimalField, F, Max, OuterRef, Prefetch, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from core.auth import gym_staff_auth
from fitness.attendance import attendance_data, class_headcount, desk_member, list_today_visits, lookup_members, member_card_code, open_visit_today, qr_response, require_checkin_member
from fitness.exports import cash_log_pdf_response, cash_log_xlsx_response, monthly_pdf_response, monthly_xlsx_response
from fitness.models import Attendance, ClassMember, ExpenseCategory, FitnessClassType, GymExpense, GymNotification, GymNotificationSettings, GymPayment, GymWhatsAppReminder, Membership, MembershipPlan, PaymentStatusOverride, Trainer, TrainerPayroll, TrainingClass
from fitness.receipts import receipt_html_response, receipt_number, receipt_pdf_response
from fitness.schemas import AttendanceCheckOutIn, AttendanceDeskOut, AttendanceIn, AttendanceLookupOut, AttendanceOut, ClassMemberIn, ClassMemberOut, ClassRevenueReportOut, ExpenseCategoryTotalOut, GymExpenseIn, GymExpenseOut, GymPaymentIn, GymPaymentOut, MemberClassIn, MemberClassOut, MemberIn, MemberOut, MembershipIn, MembershipOut, MembershipPriceIn, MembershipRemainingIn, MonthlyOverviewOut, NotificationOut, NotificationSettingsIn, NotificationSettingsOut, PaymentStatusUpdateIn, PlanIn, PlanOut, TrainerIn, TrainerOut, TrainerPayrollIn, TrainerPayrollReportOut, TrainingClassIn, TrainingClassOut, WhatsAppReminderListOut, WhatsAppReminderOut, WhatsAppReminderSentIn
from users.models import ClientProfile


router = Router(auth=gym_staff_auth)


def _require_settings_admin(request):
    if not request.user.is_authenticated or not (request.user.is_superuser or request.user.is_staff):
        raise HttpError(403, "You don't have permission to change notification settings.")


ADMIN_GROUPS = ['Admin', 'Super Admin']
ADMIN_ONLY_NOTIFICATION_TITLES = (
    'Trainer added',
    'Trainer payroll updated',
    'Expense recorded',
)


def _staff_display_name(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return ''
    return (user.get_full_name() or '').strip() or user.username


def _received_by_for_payment(request, sent: str) -> str:
    staff = _staff_display_name(request.user)
    cleaned = (sent or '').strip()
    if not cleaned or cleaned.lower() == 'admin':
        return staff or cleaned or 'Admin'
    return cleaned


def _is_gym_admin(user):
    if not user or not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', True):
        return False
    if user.is_superuser:
        return True
    group = user.groups.first()
    if group is None:
        return bool(user.is_staff)
    return group.name in ADMIN_GROUPS


def _require_gym_admin(request):
    if not _is_gym_admin(request.user):
        raise HttpError(403, 'Only an administrator can manage this.')


def _report_period(year: Optional[int], month: Optional[int]):
    today = timezone.localdate()
    year = year or today.year
    month = month or today.month
    if month < 1 or month > 12:
        raise HttpError(400, 'Month must be between 1 and 12')
    if year < 2000 or year > today.year + 1:
        raise HttpError(400, 'Year is out of range')
    return year, month


def trainer_data(trainer, year, month, payroll=None):
    payroll = payroll or trainer.payrolls.filter(year=year, month=month).first()
    return {
        'id': trainer.id,
        'first_name': trainer.first_name,
        'last_name': trainer.last_name,
        'specialization': trainer.specialization,
        'phone': trainer.phone,
        'is_active': trainer.is_active,
        'monthly_pay': trainer.monthly_pay,
        'pay_amount': payroll.pay_amount if payroll else trainer.monthly_pay,
        'is_paid': payroll.is_paid if payroll else False,
        'year': year,
        'month': month,
    }


def _upsert_trainer_payroll(trainer, year, month, pay_amount=None, is_paid=None, notes=None):
    amount = pay_amount if pay_amount is not None else trainer.monthly_pay
    payroll, created = TrainerPayroll.objects.get_or_create(
        trainer=trainer,
        year=year,
        month=month,
        defaults={
            'pay_amount': amount,
            'is_paid': bool(is_paid),
            'notes': notes or '',
        },
    )
    if created:
        if payroll.is_paid:
            payroll.paid_at = timezone.now()
            payroll.save(update_fields=['paid_at', 'updated_at'])
        return payroll
    if pay_amount is not None:
        payroll.pay_amount = pay_amount
    if notes is not None:
        payroll.notes = notes
    if is_paid is not None:
        payroll.is_paid = is_paid
        payroll.paid_at = timezone.now() if is_paid else None
    payroll.save()
    return payroll


@router.get('/notifications/settings', response=NotificationSettingsOut)
def get_notification_settings(request):
    _require_settings_admin(request)
    return GymNotificationSettings.objects.first() or GymNotificationSettings.objects.create()


@router.put('/notifications/settings', response=NotificationSettingsOut)
def update_notification_settings(request, payload: NotificationSettingsIn):
    _require_settings_admin(request)
    settings, _ = GymNotificationSettings.objects.get_or_create(pk=1)
    for field, value in payload.model_dump().items():
        setattr(settings, field, value)
    settings.save()
    return settings


STAFF_GROUPS = ['Super Admin', 'Admin', 'Reception', 'Trainer']


def staff_recipients():
    return list(User.objects.filter(Q(is_staff=True) | Q(is_superuser=True) | Q(groups__name__in=STAFF_GROUPS), is_active=True).distinct())


def admin_recipients():
    return [user for user in staff_recipients() if _is_gym_admin(user)]


def create_gym_notifications(event, category, title, message, member_id=None, actor=None, admin_only=False):
    settings = GymNotificationSettings.objects.first() or GymNotificationSettings.objects.create()
    if not getattr(settings, event, False):
        return
    recipients = admin_recipients() if admin_only else staff_recipients()
    if (
        actor
        and getattr(actor, 'is_authenticated', False)
        and getattr(actor, 'is_active', False)
        and actor.id not in {user.id for user in recipients}
        and (not admin_only or _is_gym_admin(actor))
    ):
        recipients.append(actor)
    if not recipients:
        return
    GymNotification.objects.bulk_create([GymNotification(recipient=user, category=category, title=title, message=message, member_id=member_id) for user in recipients])


def _membership_event_notifications(event, title, memberships, message_for):
    settings = GymNotificationSettings.objects.first() or GymNotificationSettings.objects.create()
    if not getattr(settings, event, False):
        return
    today = timezone.localdate()
    recipients = staff_recipients()
    if not recipients:
        return
    for membership in memberships:
        message = message_for(membership)
        existing = GymNotification.objects.filter(member_id=membership.member_id, title=title, created_at__date=today).exists()
        if existing:
            continue
        GymNotification.objects.bulk_create([GymNotification(recipient=user, category='memberships', title=title, message=message, member_id=membership.member_id) for user in recipients])


def create_expiring_membership_notifications():
    today = timezone.localdate()
    expiry_date = today + timedelta(days=7)
    memberships = Membership.objects.select_related('member__user').filter(end_date=expiry_date, status_override='')
    _membership_event_notifications(
        'membership_expiring_soon',
        'Membership expiring soon',
        memberships,
        lambda membership: f"{membership.member.user.get_full_name()} membership expires on {membership.end_date.strftime('%d %b %Y')} (7 days remaining).",
    )


def create_expired_membership_notifications():
    today = timezone.localdate()
    memberships = Membership.objects.select_related('member__user').filter(end_date=today - timedelta(days=1), status_override='')
    _membership_event_notifications(
        'membership_expired',
        'Membership expired',
        memberships,
        lambda membership: f"{membership.member.user.get_full_name()} membership expired on {membership.end_date.strftime('%d %b %Y')}.",
    )


@router.get('/notifications', response=List[NotificationOut])
def list_notifications(request, category: Optional[str] = None, unread: bool = False):
    if not request.user.is_authenticated:
        raise HttpError(401, 'Authentication required.')
    create_expiring_membership_notifications()
    create_expired_membership_notifications()
    queryset = GymNotification.objects.filter(recipient=request.user).order_by('-created_at')
    if not _is_gym_admin(request.user):
        queryset = queryset.exclude(title__in=ADMIN_ONLY_NOTIFICATION_TITLES)
    if category:
        queryset = queryset.filter(category=category)
    if unread:
        queryset = queryset.filter(is_read=False)
    return list(queryset[:200])


@router.patch('/notifications/{notification_id}/read', response=NotificationOut)
def mark_notification_read(request, notification_id: int):
    if not request.user.is_authenticated:
        raise HttpError(401, 'Authentication required.')
    try:
        notification = GymNotification.objects.get(id=notification_id, recipient=request.user)
    except GymNotification.DoesNotExist:
        raise HttpError(404, 'Notification not found.')
    notification.is_read = True
    notification.save(update_fields=['is_read', 'updated_at'])
    return notification


@router.post('/notifications/read-all')
def mark_all_notifications_read(request):
    if not request.user.is_authenticated:
        raise HttpError(401, 'Authentication required.')
    GymNotification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return {'success': True}


@router.delete('/notifications')
def delete_all_notifications(request):
    if not request.user.is_authenticated:
        raise HttpError(401, 'Authentication required.')
    GymNotification.objects.filter(recipient=request.user).delete()
    return {'success': True}


@router.delete('/notifications/{notification_id}')
def delete_notification(request, notification_id: int):
    if not request.user.is_authenticated:
        raise HttpError(401, 'Authentication required.')
    deleted, _ = GymNotification.objects.filter(id=notification_id, recipient=request.user).delete()
    if not deleted:
        raise HttpError(404, 'Notification not found.')
    return {'success': True}


def class_data(training_class):
    return {
        'id': training_class.id,
        'name': training_class.name,
        'class_type': training_class.class_type,
        'price_per_member': training_class.price_per_member,
        'member_count': training_class.member_count,
        'team_total': training_class.team_total,
        'is_active': training_class.is_active,
    }


def _class_type_or_400(class_type):
    valid_types = {choice for choice, _ in FitnessClassType.choices}
    if class_type not in valid_types:
        raise HttpError(400, 'class_type must be boxing, musculation, aerobic, or kick_boxing')
    return class_type


def _apply_class_payload(training_class, payload):
    name = (payload.name or '').strip()
    if not name:
        raise HttpError(400, 'Class name is required')
    training_class.name = name
    training_class.class_type = _class_type_or_400(payload.class_type)
    training_class.price_per_member = payload.price_per_member
    training_class.is_active = payload.is_active
    try:
        with transaction.atomic():
            training_class.save()
    except IntegrityError:
        raise HttpError(409, 'A class with this name and type already exists')
    return training_class


def _get_training_class(class_id):
    try:
        return TrainingClass.objects.get(id=class_id)
    except TrainingClass.DoesNotExist:
        raise HttpError(404, 'Fitness class not found')


def _plan_queryset():
    return MembershipPlan.objects.annotate(member_count=Count('memberships__member', distinct=True))


def plan_data(plan):
    return {
        'id': plan.id,
        'name': plan.name,
        'duration_months': plan.duration_months,
        'price': plan.price,
        'description': plan.description,
        'is_active': plan.is_active,
        'member_count': int(getattr(plan, 'member_count', 0) or 0),
    }


def _get_plan(plan_id):
    try:
        return _plan_queryset().get(id=plan_id)
    except MembershipPlan.DoesNotExist:
        raise HttpError(404, 'Membership plan not found')


def _apply_plan_payload(plan, payload):
    name = (payload.name or '').strip()
    if not name:
        raise HttpError(400, 'Plan name is required')
    plan.name = name
    plan.duration_months = payload.duration_months
    plan.price = payload.price
    plan.description = payload.description or ''
    plan.is_active = payload.is_active
    try:
        with transaction.atomic():
            plan.save()
    except IntegrityError:
        raise HttpError(409, 'A plan with this name already exists')
    return _get_plan(plan.id)


@router.get('/fitness/classes', response=List[TrainingClassOut])
def list_classes(request):
    return [class_data(item) for item in TrainingClass.objects.prefetch_related('members__client')]


@router.post('/fitness/classes', response=TrainingClassOut)
def create_class(request, payload: TrainingClassIn):
    _require_gym_admin(request)
    return class_data(_apply_class_payload(TrainingClass(), payload))


@router.put('/fitness/classes/{class_id}', response=TrainingClassOut)
def update_class(request, class_id: int, payload: TrainingClassIn):
    _require_gym_admin(request)
    return class_data(_apply_class_payload(_get_training_class(class_id), payload))


@router.delete('/fitness/classes/{class_id}')
def delete_class(request, class_id: int):
    _require_gym_admin(request)
    _get_training_class(class_id).delete()
    return {'success': True}


@router.get('/fitness/classes/{class_id}', response=TrainingClassOut)
def get_class(request, class_id: int):
    return class_data(_get_training_class(class_id))


@router.post('/fitness/classes/{class_id}/members', response=ClassMemberOut)
def add_member(request, class_id: int, payload: ClassMemberIn):
    try:
        training_class = TrainingClass.objects.get(id=class_id)
        client = ClientProfile.objects.get(id=payload.client_id)
    except (TrainingClass.DoesNotExist, ClientProfile.DoesNotExist):
        raise HttpError(404, 'Fitness class or client not found')

    assignment = ClassMember.objects.filter(training_class=training_class, client=client).first()
    if assignment:
        if assignment.is_active:
            raise HttpError(400, 'Client is already a member of this class')
        assignment.is_active = True
        assignment.save(update_fields=['is_active', 'updated_at'])
        return assignment

    return ClassMember.objects.create(training_class=training_class, client=client)


@router.delete('/fitness/classes/{class_id}/members/{member_id}')
def remove_member(request, class_id: int, member_id: int):
    deleted, _ = ClassMember.objects.filter(
        id=member_id,
        training_class_id=class_id,
    ).delete()
    if not deleted:
        raise HttpError(404, 'Class member not found')
    return {'success': True}


def member_data(member):
    assignment = None
    cached = getattr(member, 'active_classes', None)
    if cached is not None:
        assignment = cached[0] if cached else None
    else:
        assignment = ClassMember.objects.filter(client_id=member.id, is_active=True).select_related('training_class').first()
    return {
        'id': member.id,
        'name': f'{member.user.first_name} {member.user.last_name}'.strip(),
        'phone': member.phone,
        'email': member.user.email,
        'id_number': member.id_number or '',
        'address': member.address,
        'city': member.city,
        'country': member.country,
        'postal_code': member.postal_code,
        'card_code': member_card_code(member.id),
        'class_id': assignment.training_class_id if assignment else None,
        'class_name': assignment.training_class.name if assignment else '',
    }


def _paid_total_annotation():
    zero = Decimal('0.00')
    return Coalesce(
        Sum('payments__amount', filter=Q(payments__status='paid')),
        Value(zero),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )


def _memberships_with_paid_total():
    return Membership.objects.select_related('member__user', 'plan').annotate(paid_total=_paid_total_annotation())


def _membership_paid_total(item):
    paid = getattr(item, 'paid_total', None)
    if paid is not None:
        return paid or Decimal('0.00')
    cache = getattr(item, '_prefetched_objects_cache', None)
    if cache and 'payments' in cache:
        return sum((payment.amount for payment in item.payments.all() if payment.status == 'paid'), Decimal('0.00'))
    return item.payments.filter(status='paid').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')


def membership_data(item):
    paid = _membership_paid_total(item)
    remaining = max(item.price - paid, Decimal('0.00'))
    if item.payment_status_override:
        payment_status = item.payment_status_override
    elif paid >= item.price:
        payment_status = 'paid'
    elif paid > 0:
        payment_status = 'partial'
    else:
        payment_status = 'unpaid'
    return {
        'id': item.id,
        'member_id': item.member_id,
        'plan_id': item.plan_id,
        'start_date': item.start_date,
        'end_date': item.end_date,
        'price': item.price,
        'status': item.status,
        'payment_status': payment_status,
        'total_paid': paid,
        'remaining_balance': remaining,
        'notes': item.notes,
    }


def _reminder_membership_qs():
    """Memberships that need a WhatsApp reminder, with paid_total annotated."""
    today = timezone.localdate()
    expired_after = today - timedelta(days=60)
    expiring_until = today + timedelta(days=7)
    return (
        _memberships_with_paid_total()
        .exclude(status_override__in=('cancelled', 'suspended'))
        .filter(
            Q(price__gt=F('paid_total'))
            | Q(start_date__lte=today, end_date__gte=today, end_date__lte=expiring_until)
            | Q(end_date__gte=expired_after, end_date__lt=today)
        )
    )


def payment_data(payment):
    membership = payment.membership
    member = membership.member
    user = member.user
    name = f'{user.first_name} {user.last_name}'.strip() or user.username
    paid = getattr(payment, 'paid_total', None)
    remaining = max(membership.price - paid, Decimal('0.00')) if paid is not None else membership.remaining_balance
    return {
        'id': payment.id,
        'membership_id': payment.membership_id,
        'member_id': membership.member_id,
        'member_name': name,
        'id_number': member.id_number or '',
        'amount': payment.amount,
        'payment_method': payment.payment_method,
        'received_by': payment.received_by,
        'received_at': payment.received_at,
        'notes': payment.notes,
        'remaining_balance': remaining,
        'receipt_number': receipt_number(payment),
    }


def _payment_queryset():
    paid_sub = (
        GymPayment.objects.filter(membership_id=OuterRef('membership_id'), status='paid')
        .values('membership_id')
        .annotate(total=Sum('amount'))
        .values('total')[:1]
    )
    return GymPayment.objects.select_related('membership__member__user').annotate(
        paid_total=Coalesce(
            Subquery(paid_sub, output_field=DecimalField(max_digits=10, decimal_places=2)),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        )
    )


def _filter_payments(qs, q=None, year=None, month=None):
    if year or month:
        year, month = _report_period(year, month)
        qs = qs.filter(received_at__year=year, received_at__month=month)
    needle = (q or '').strip()
    if needle:
        digits = re.sub(r'\D', '', needle)
        lookup = (
            Q(membership__member__user__first_name__icontains=needle)
            | Q(membership__member__user__last_name__icontains=needle)
            | Q(membership__member__id_number__icontains=needle)
            | Q(membership__member__phone__icontains=needle)
            | Q(notes__icontains=needle)
            | Q(received_by__icontains=needle)
        )
        if digits:
            lookup |= Q(id=int(digits)) if digits.isdigit() else Q()
        qs = qs.filter(lookup)
    return qs, year, month


def _cash_log_rows(payments):
    rows = []
    total = Decimal('0.00')
    for payment in payments:
        data = payment_data(payment)
        received = timezone.localtime(payment.received_at) if timezone.is_aware(payment.received_at) else payment.received_at
        rows.append({
            **data,
            'received_at': received.strftime('%Y-%m-%d %H:%M'),
            'payment_method': 'Cash',
        })
        total += payment.amount
    return rows, total


def _get_payment_or_404(payment_id):
    try:
        return _payment_queryset().get(id=payment_id)
    except GymPayment.DoesNotExist:
        raise HttpError(404, 'Payment not found')


def morocco_whatsapp_number(phone: str) -> str:
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('00'):
        digits = digits[2:]
    if not digits:
        return ''
    if digits.startswith('212') and len(digits) >= 12:
        return digits
    if digits.startswith('0') and len(digits) == 10:
        return '212' + digits[1:]
    if len(digits) == 9 and digits[0] in '567':
        return '212' + digits
    return digits if len(digits) >= 9 else ''


def reminder_message(name, reasons, end_date, days_left, remaining):
    first = (name or '').split()[0] or 'bonjour'
    date_label = end_date.strftime('%d/%m/%Y')
    parts = [f'Bonjour {first},']
    if 'expiring_soon' in reasons:
        days = max(int(days_left), 0)
        day_word = 'jour' if days == 1 else 'jours'
        parts.append(f'votre abonnement expire le {date_label} ({days} {day_word}).')
    elif 'expired' in reasons:
        parts.append(f'votre abonnement a expire le {date_label}.')
    if 'unpaid' in reasons:
        parts.append(f'Il reste {remaining:.2f} MAD a regler.')
    parts.append('Merci de passer au gym. FlexOper')
    return ' '.join(parts)


def _reminder_rows():
    today = timezone.localdate()
    expired_after = today - timedelta(days=60)
    zero = Decimal('0.00')
    memberships = list(_reminder_membership_qs())
    latest = {
        row['membership_id']: row['sent_at']
        for row in GymWhatsAppReminder.objects.values('membership_id').annotate(sent_at=Max('created_at'))
    }
    items = []
    for item in memberships:
        remaining = max(item.price - (item.paid_total or zero), zero)
        reasons = []
        if item.status == 'expiring_soon':
            reasons.append('expiring_soon')
        if item.status == 'expired' and item.end_date >= expired_after:
            reasons.append('expired')
        if remaining > 0:
            reasons.append('unpaid')
        if not reasons:
            continue
        name = f'{item.member.user.first_name} {item.member.user.last_name}'.strip()
        phone = item.member.phone or ''
        number = morocco_whatsapp_number(phone)
        days_left = (item.end_date - today).days
        message = reminder_message(name, reasons, item.end_date, days_left, remaining)
        last_sent = latest.get(item.id)
        sent_date = None
        if last_sent:
            sent_date = timezone.localtime(last_sent).date() if timezone.is_aware(last_sent) else last_sent.date()
        if remaining > 0:
            pay_status = 'partial' if (item.paid_total or zero) > 0 else 'unpaid'
        else:
            pay_status = 'paid'
        if item.payment_status_override:
            pay_status = item.payment_status_override
        items.append({
            'membership_id': item.id,
            'member_id': item.member_id,
            'member_name': name,
            'phone': phone,
            'whatsapp_url': f'https://wa.me/{number}?text={quote(message)}' if number else None,
            'status': item.status,
            'payment_status': pay_status,
            'end_date': item.end_date,
            'days_left': days_left,
            'remaining': remaining,
            'reasons': reasons,
            'message': message,
            'last_sent_at': last_sent,
            'reminded_today': sent_date == today,
        })
    items.sort(key=lambda row: (
        row['reminded_today'],
        not row['whatsapp_url'],
        0 if 'expiring_soon' in row['reasons'] else 1 if 'unpaid' in row['reasons'] else 2,
        row['days_left'],
        row['member_name'].lower(),
    ))
    return items


@router.get('/fitness/dashboard')
def gym_dashboard(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    memberships = Membership.objects.all()
    active = memberships.filter(start_date__lte=today, end_date__gte=today).count()
    expiring = memberships.filter(end_date=today + timedelta(days=7)).count()
    payments = GymPayment.objects.filter(status='paid', received_at__date__gte=month_start)
    paid_totals = memberships.annotate(paid_total=Sum('payments__amount', filter=Q(payments__status='paid'))).values_list('price', 'paid_total')
    outstanding = sum((max(price - (paid or Decimal('0.00')), Decimal('0.00')) for price, paid in paid_totals), Decimal('0.00'))
    recent_members = ClientProfile.objects.select_related('user').order_by('-created_at')[:5]
    reminder_count = _reminder_membership_qs().count()
    return {'members': ClientProfile.objects.filter(is_active=True).count(), 'active_members': active, 'expiring_soon': expiring, 'cash_this_month': payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'), 'outstanding': outstanding, 'whatsapp_due': reminder_count, 'recent_members': [member_data(item) for item in recent_members]}


@router.get('/fitness/reports/classes', response=ClassRevenueReportOut)
def class_revenue_report(request, year: Optional[int] = None, month: Optional[int] = None):
    today = timezone.localdate()
    year = year or today.year
    month = month or today.month
    if month < 1 or month > 12:
        raise HttpError(400, 'Month must be between 1 and 12')
    if year < 2000 or year > today.year + 1:
        raise HttpError(400, 'Year is out of range')

    zero = Decimal('0.00')
    assignments = {
        row['client_id']: row['training_class_id']
        for row in ClassMember.objects.filter(is_active=True, client__is_active=True).values('client_id', 'training_class_id')
    }
    collected_by_member = {
        row['membership__member_id']: row['total'] or zero
        for row in GymPayment.objects.filter(
            status='paid',
            received_at__year=year,
            received_at__month=month,
        ).values('membership__member_id').annotate(total=Sum('amount'))
    }
    outstanding_by_member = {}
    membership_rows = Membership.objects.annotate(
        paid_total=Coalesce(
            Sum('payments__amount', filter=Q(payments__status='paid')),
            Value(zero),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    ).values('member_id', 'price', 'paid_total')
    for row in membership_rows:
        remaining = max(row['price'] - (row['paid_total'] or zero), zero)
        if remaining:
            outstanding_by_member[row['member_id']] = outstanding_by_member.get(row['member_id'], zero) + remaining

    def totals_for(member_ids):
        collected = sum((collected_by_member.get(member_id, zero) for member_id in member_ids), zero)
        outstanding = sum((outstanding_by_member.get(member_id, zero) for member_id in member_ids), zero)
        return collected, outstanding

    classes = []
    for training_class in TrainingClass.objects.prefetch_related('members__client'):
        member_ids = [member_id for member_id, class_id in assignments.items() if class_id == training_class.id]
        collected, outstanding = totals_for(member_ids)
        member_count = training_class.member_count
        expected = training_class.price_per_member * member_count
        classes.append({
            'id': training_class.id,
            'name': training_class.name,
            'class_type': training_class.class_type,
            'class_type_label': training_class.get_class_type_display(),
            'member_count': member_count,
            'price_per_member': training_class.price_per_member,
            'expected_monthly': expected,
            'collected': collected,
            'outstanding': outstanding,
        })

    unassigned_ids = set(collected_by_member) | set(outstanding_by_member)
    unassigned_ids -= set(assignments)
    if unassigned_ids:
        collected, outstanding = totals_for(unassigned_ids)
        classes.append({
            'id': None,
            'name': 'Unassigned members',
            'class_type': '',
            'class_type_label': 'No class',
            'member_count': len(unassigned_ids),
            'price_per_member': zero,
            'expected_monthly': zero,
            'collected': collected,
            'outstanding': outstanding,
        })

    classes.sort(key=lambda item: (-item['collected'], item['name'].lower()))
    total_expected = sum((item['expected_monthly'] for item in classes), zero)
    total_collected = sum((item['collected'] for item in classes), zero)
    total_outstanding = sum((item['outstanding'] for item in classes), zero)
    collection_rate = (total_collected / total_expected * Decimal('100')).quantize(Decimal('0.1')) if total_expected else zero
    return {
        'year': year,
        'month': month,
        'label': f'{month_name[month]} {year}',
        'total_expected': total_expected,
        'total_collected': total_collected,
        'total_outstanding': total_outstanding,
        'collection_rate': collection_rate,
        'classes': classes,
    }


@router.get('/fitness/members', response=List[MemberOut])
def list_members(request, search: Optional[str] = None):
    queryset = ClientProfile.objects.select_related('user').filter(is_active=True).prefetch_related(
        Prefetch(
            'fitness_memberships',
            queryset=ClassMember.objects.filter(is_active=True).select_related('training_class'),
            to_attr='active_classes',
        )
    )
    if search:
        queryset = queryset.filter(
            Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(user__email__icontains=search)
            | Q(id_number__icontains=search)
            | Q(address__icontains=search)
        )
    return [member_data(item) for item in queryset[:500]]


@router.get('/fitness/members/{member_id}', response=MemberOut)
def get_member(request, member_id: int):
    try:
        member = ClientProfile.objects.select_related('user').get(id=member_id)
    except ClientProfile.DoesNotExist:
        raise HttpError(404, 'Member not found')
    return member_data(member)


def _normalize_cin(value):
    return re.sub(r'[\s\-]', '', value or '').upper()


def _member_identity(payload, required=True):
    cin = _normalize_cin(payload.id_number)
    address = (payload.address or '').strip()
    city = (payload.city or '').strip()
    if required:
        if not cin:
            raise HttpError(400, 'CIN is required')
        if len(cin) < 5 or not re.fullmatch(r'[A-Z0-9]+', cin):
            raise HttpError(400, 'CIN should be the Moroccan national card number, letters and digits only')
        if not address:
            raise HttpError(400, 'Address is required')
    return cin, address, city


@router.post('/fitness/members', response=MemberOut)
def create_member(request, payload: MemberIn):
    cin, address, city = _member_identity(payload, required=True)
    username = f'gym_{payload.first_name.lower()}_{payload.last_name.lower()}_{User.objects.count() + 1}'
    user = User.objects.create_user(username=username, first_name=payload.first_name.strip(), last_name=payload.last_name.strip(), email=payload.email)
    try:
        with transaction.atomic():
            member = ClientProfile.objects.create(
                user=user,
                phone=payload.phone.strip(),
                address=address,
                city=city,
                country=(payload.country or 'Morocco').strip() or 'Morocco',
                postal_code=(payload.postal_code or '').strip(),
                id_number=cin,
            )
    except IntegrityError:
        user.delete()
        raise HttpError(409, 'A member with this CIN already exists')
    create_gym_notifications('new_member_registered', 'members', 'New member registered', f'{member.user.get_full_name()} joined the gym.', member.id, request.user)
    return member_data(member)


@router.put('/fitness/members/{member_id}', response=MemberOut)
def update_member(request, member_id: int, payload: MemberIn):
    try:
        member = ClientProfile.objects.select_related('user').get(id=member_id)
    except ClientProfile.DoesNotExist:
        raise HttpError(404, 'Member not found')

    cin, address, city = _member_identity(payload, required=True)
    member.phone = payload.phone.strip()
    member.address = address
    member.city = city
    member.country = (payload.country or 'Morocco').strip() or 'Morocco'
    member.postal_code = (payload.postal_code or '').strip()
    member.id_number = cin
    member.user.first_name = payload.first_name.strip()
    member.user.last_name = payload.last_name.strip()
    member.user.email = payload.email
    try:
        with transaction.atomic():
            member.user.save()
            member.save()
    except IntegrityError:
        raise HttpError(409, 'A member with this CIN already exists')
    create_gym_notifications('member_updated', 'members', 'Member updated', f'{member.user.get_full_name()} details were updated.', member.id, request.user)
    return member_data(member)


def _member_class_data(member_id, assignment=None):
    if assignment is None:
        assignment = ClassMember.objects.filter(client_id=member_id, is_active=True).first()
    if not assignment:
        return {'id': None, 'training_class_id': None, 'client_id': member_id}
    return {'id': assignment.id, 'training_class_id': assignment.training_class_id, 'client_id': member_id}


@router.get('/fitness/members/{member_id}/class', response=MemberClassOut)
def get_member_class(request, member_id: int):
    if not ClientProfile.objects.filter(id=member_id).exists():
        raise HttpError(404, 'Member not found')
    return _member_class_data(member_id)


@router.put('/fitness/members/{member_id}/class', response=MemberClassOut)
def set_member_class(request, member_id: int, payload: MemberClassIn):
    if not ClientProfile.objects.filter(id=member_id).exists():
        raise HttpError(404, 'Member not found')

    if payload.class_id is None:
        ClassMember.objects.filter(client_id=member_id, is_active=True).update(is_active=False)
        return _member_class_data(member_id)

    try:
        training_class = TrainingClass.objects.get(id=payload.class_id)
    except TrainingClass.DoesNotExist:
        raise HttpError(404, 'Fitness class not found')

    ClassMember.objects.filter(client_id=member_id, is_active=True).exclude(training_class_id=payload.class_id).update(is_active=False)
    assignment, _created = ClassMember.objects.get_or_create(
        training_class=training_class,
        client_id=member_id,
        defaults={'is_active': True},
    )
    if not assignment.is_active:
        assignment.is_active = True
        assignment.save(update_fields=['is_active', 'updated_at'])
    return _member_class_data(member_id, assignment)


@router.delete('/fitness/members/{member_id}')
def delete_member(request, member_id: int):
    try:
        member = ClientProfile.objects.select_related('user').get(id=member_id, is_active=True)
    except ClientProfile.DoesNotExist:
        raise HttpError(404, 'Member not found')
    member.is_active = False
    member.save(update_fields=['is_active', 'updated_at'])
    ClassMember.objects.filter(client_id=member_id, is_active=True).update(is_active=False)
    create_gym_notifications('member_deactivated', 'members', 'Member deactivated', f'{member.user.get_full_name()} was deactivated.', member.id, request.user)
    return {'success': True}


@router.get('/fitness/plans', response=List[PlanOut])
def list_plans(request):
    return [plan_data(item) for item in _plan_queryset()]


@router.post('/fitness/plans', response=PlanOut)
def create_plan(request, payload: PlanIn):
    _require_gym_admin(request)
    return plan_data(_apply_plan_payload(MembershipPlan(), payload))


@router.put('/fitness/plans/{plan_id}', response=PlanOut)
def update_plan(request, plan_id: int, payload: PlanIn):
    _require_gym_admin(request)
    return plan_data(_apply_plan_payload(_get_plan(plan_id), payload))


@router.delete('/fitness/plans/{plan_id}')
def delete_plan(request, plan_id: int):
    _require_gym_admin(request)
    plan = _get_plan(plan_id)
    try:
        plan.delete()
    except ProtectedError:
        raise HttpError(400, 'This plan is used by memberships. Deactivate it instead of deleting.')
    return {'success': True}


@router.get('/fitness/memberships', response=List[MembershipOut])
def list_memberships(request, status: Optional[str] = None):
    queryset = _memberships_with_paid_total()
    items = [item for item in queryset if not status or item.status == status]
    return [membership_data(item) for item in items[:500]]


@router.get('/fitness/memberships/expiring', response=List[MembershipOut])
def expiring_memberships(request):
    today = timezone.localdate()
    queryset = _memberships_with_paid_total().filter(
        status_override='',
        start_date__lte=today,
        end_date__gte=today,
        end_date__lte=today + timedelta(days=7),
    )
    return [membership_data(item) for item in queryset]


@router.get('/fitness/reminders', response=WhatsAppReminderListOut)
def list_whatsapp_reminders(request):
    items = _reminder_rows()
    return {
        'expiring': sum(1 for item in items if 'expiring_soon' in item['reasons']),
        'expired': sum(1 for item in items if 'expired' in item['reasons']),
        'unpaid': sum(1 for item in items if 'unpaid' in item['reasons']),
        'missing_phone': sum(1 for item in items if not item['whatsapp_url']),
        'items': items,
    }


@router.post('/fitness/reminders/{membership_id}/sent', response=WhatsAppReminderOut)
def mark_whatsapp_reminder_sent(request, membership_id: int, payload: WhatsAppReminderSentIn):
    try:
        membership = Membership.objects.select_related('member__user', 'plan').get(id=membership_id)
    except Membership.DoesNotExist:
        raise HttpError(404, 'Membership not found')
    rows = [item for item in _reminder_rows() if item['membership_id'] == membership_id]
    if not rows:
        raise HttpError(400, 'This membership does not need a reminder right now.')
    row = rows[0]
    sent_by = request.user.get_full_name().strip() or request.user.username
    GymWhatsAppReminder.objects.create(
        membership=membership,
        kind=','.join(row['reasons']),
        message=payload.message.strip() or row['message'],
        sent_by=sent_by,
    )
    refreshed = [item for item in _reminder_rows() if item['membership_id'] == membership_id]
    return refreshed[0] if refreshed else {**row, 'reminded_today': True, 'last_sent_at': timezone.now()}


@router.post('/fitness/memberships', response=MembershipOut)
def create_membership(request, payload: MembershipIn):
    try:
        member = ClientProfile.objects.get(id=payload.member_id)
        plan = MembershipPlan.objects.get(id=payload.plan_id, is_active=True)
    except (ClientProfile.DoesNotExist, MembershipPlan.DoesNotExist):
        raise HttpError(404, 'Member or plan not found')
    item = Membership.objects.create(member=member, plan=plan, start_date=payload.start_date, end_date=payload.start_date + timedelta(days=30 * plan.duration_months), price=payload.price if payload.price is not None else plan.price, notes=payload.notes)
    create_gym_notifications('new_membership_created', 'memberships', 'New membership created', f'{member.user.get_full_name()} started {plan.name}.', member.id, request.user)
    return membership_data(item)


@router.put('/fitness/memberships/{membership_id}', response=MembershipOut)
def update_membership(request, membership_id: int, payload: MembershipIn):
    try:
        item = Membership.objects.get(id=membership_id)
        member = ClientProfile.objects.get(id=payload.member_id)
        plan = MembershipPlan.objects.get(id=payload.plan_id, is_active=True)
    except (Membership.DoesNotExist, ClientProfile.DoesNotExist, MembershipPlan.DoesNotExist):
        raise HttpError(404, 'Membership, member, or plan not found')

    previous_plan_id = item.plan_id
    item.member = member
    item.plan = plan
    item.start_date = payload.start_date
    item.end_date = payload.start_date + timedelta(days=30 * plan.duration_months)
    if payload.price is not None:
        item.price = payload.price
    elif previous_plan_id != plan.id:
        item.price = plan.price
    item.notes = payload.notes
    item.save()
    create_gym_notifications('important_system_alerts', 'memberships', 'Membership updated', f'{member.user.get_full_name()} membership was updated.', member.id, request.user)
    return membership_data(item)


@router.delete('/fitness/memberships/{membership_id}')
def delete_membership(request, membership_id: int):
    try:
        item = Membership.objects.select_related('member__user', 'plan').get(id=membership_id)
    except Membership.DoesNotExist:
        raise HttpError(404, 'Membership not found')
    member_id = item.member_id
    message = f'{item.member.user.get_full_name()} {item.plan.name} membership was deleted.'
    item.delete()
    create_gym_notifications('important_system_alerts', 'memberships', 'Membership deleted', message, member_id, request.user)
    return {'success': True}


@router.patch('/fitness/memberships/{membership_id}/price', response=MembershipOut)
def update_membership_price(request, membership_id: int, payload: MembershipPriceIn):
    try:
        item = Membership.objects.select_related('member__user').get(id=membership_id)
    except Membership.DoesNotExist:
        raise HttpError(404, 'Membership not found')
    item.price = payload.price
    item.save(update_fields=['price', 'updated_at'])
    create_gym_notifications(
        'important_system_alerts',
        'memberships',
        'Membership price updated',
        f'{item.member.user.get_full_name()} membership price was set to {item.price} MAD.',
        item.member_id,
        request.user,
    )
    return membership_data(item)


@router.patch('/fitness/memberships/{membership_id}/remaining', response=MembershipOut)
def update_membership_remaining(request, membership_id: int, payload: MembershipRemainingIn):
    try:
        item = Membership.objects.select_related('member__user').prefetch_related('payments').get(id=membership_id)
    except Membership.DoesNotExist:
        raise HttpError(404, 'Membership not found')
    item.price = item.total_paid + payload.remaining
    item.payment_status_override = ''
    item.save(update_fields=['price', 'payment_status_override', 'updated_at'])
    create_gym_notifications(
        'outstanding_payment' if payload.remaining > 0 else 'payment_received',
        'payments',
        'Remaining balance updated',
        f'{item.member.user.get_full_name()} remaining balance was set to {payload.remaining} MAD.',
        item.member_id,
        request.user,
    )
    return membership_data(item)


@router.patch('/fitness/memberships/{membership_id}/payment-status', response=MembershipOut)
def update_payment_status(request, membership_id: int, payload: PaymentStatusUpdateIn):
    if payload.status not in (PaymentStatusOverride.PAID, PaymentStatusOverride.UNPAID):
        raise HttpError(400, 'Payment status must be paid or unpaid')
    try:
        item = Membership.objects.select_related('member__user').get(id=membership_id)
    except Membership.DoesNotExist:
        raise HttpError(404, 'Membership not found')
    item.payment_status_override = payload.status
    item.save(update_fields=['payment_status_override', 'updated_at'])
    member_name = item.member.user.get_full_name()
    if payload.status == PaymentStatusOverride.PAID:
        create_gym_notifications('payment_received', 'payments', 'Payment marked as paid', f'{member_name} membership was marked as paid.', item.member_id, request.user)
    else:
        create_gym_notifications('outstanding_payment', 'payments', 'Payment marked as unpaid', f'{member_name} membership was marked as unpaid.', item.member_id, request.user)
    return membership_data(item)


@router.post('/fitness/memberships/{membership_id}/renew', response=MembershipOut)
def renew_membership(request, membership_id: int, payload: MembershipIn):
    try:
        old = Membership.objects.get(id=membership_id)
        plan = MembershipPlan.objects.get(id=payload.plan_id, is_active=True)
    except (Membership.DoesNotExist, MembershipPlan.DoesNotExist):
        raise HttpError(404, 'Membership or plan not found')
    start = max(old.end_date, payload.start_date)
    item = Membership.objects.create(member=old.member, plan=plan, start_date=start, end_date=start + timedelta(days=30 * plan.duration_months), price=plan.price, notes=payload.notes)
    create_gym_notifications('membership_renewed', 'memberships', 'Membership renewed', f'{old.member.user.get_full_name()} renewed {plan.name}.', old.member_id, request.user)
    return membership_data(item)


@router.get('/fitness/memberships/{membership_id}/payments', response=List[GymPaymentOut])
def membership_payments(request, membership_id: int):
    return [payment_data(item) for item in _payment_queryset().filter(membership_id=membership_id)]


@router.post('/fitness/memberships/{membership_id}/payments', response=GymPaymentOut)
def record_gym_payment(request, membership_id: int, payload: GymPaymentIn):
    try:
        membership = Membership.objects.select_related('member__user').get(id=membership_id)
    except Membership.DoesNotExist:
        raise HttpError(404, 'Membership not found')
    if payload.remaining is not None:
        membership.price = membership.total_paid + payload.amount + payload.remaining
        membership.payment_status_override = ''
        membership.save(update_fields=['price', 'payment_status_override', 'updated_at'])
    elif payload.amount > membership.remaining_balance:
        raise HttpError(400, 'Payment exceeds remaining balance')
    payment = GymPayment.objects.create(
        membership=membership,
        amount=payload.amount,
        received_by=_received_by_for_payment(request, payload.received_by),
        notes=payload.notes,
    )
    member_name = membership.member.user.get_full_name()
    create_gym_notifications('payment_received', 'payments', 'Payment received', f'{member_name} paid {payment.amount} MAD.', membership.member_id, request.user)
    remaining = membership.price - membership.total_paid
    if remaining > 0:
        create_gym_notifications('partial_payment', 'payments', 'Partial payment', f'{member_name} paid {payment.amount} MAD and still has {remaining} MAD remaining.', membership.member_id, request.user)
        create_gym_notifications('outstanding_payment', 'payments', 'Outstanding payment', f'{member_name} has {remaining} MAD remaining.', membership.member_id, request.user)
    payment = _payment_queryset().get(id=payment.id)
    return payment_data(payment)


@router.get('/fitness/payments', response=List[GymPaymentOut])
def list_gym_payments(request, q: Optional[str] = None, year: Optional[int] = None, month: Optional[int] = None):
    qs, _, _ = _filter_payments(_payment_queryset(), q=q, year=year, month=month)
    if year or month:
        return [payment_data(item) for item in qs]
    return [payment_data(item) for item in qs[:500]]


@router.get('/fitness/payments/export/xlsx')
def export_cash_log_xlsx(request, year: Optional[int] = None, month: Optional[int] = None, q: Optional[str] = None):
    qs, year, month = _filter_payments(_payment_queryset(), q=q, year=year or timezone.localdate().year, month=month or timezone.localdate().month)
    year, month = _report_period(year, month)
    rows, total = _cash_log_rows(qs)
    return cash_log_xlsx_response(year, month, f'{month_name[month]} {year}', rows, total)


@router.get('/fitness/payments/export/pdf')
def export_cash_log_pdf(request, year: Optional[int] = None, month: Optional[int] = None, q: Optional[str] = None):
    qs, year, month = _filter_payments(_payment_queryset(), q=q, year=year or timezone.localdate().year, month=month or timezone.localdate().month)
    year, month = _report_period(year, month)
    rows, total = _cash_log_rows(qs)
    return cash_log_pdf_response(year, month, f'{month_name[month]} {year}', rows, total)


@router.get('/fitness/payments/{payment_id}/receipt.html')
def gym_payment_receipt_html(request, payment_id: int):
    return receipt_html_response(_get_payment_or_404(payment_id))


@router.get('/fitness/payments/{payment_id}/receipt')
def gym_payment_receipt_pdf(request, payment_id: int):
    return receipt_pdf_response(_get_payment_or_404(payment_id))


@router.get('/fitness/attendance', response=List[AttendanceOut])
def list_attendance(request):
    return list_today_visits()


@router.get('/fitness/attendance/desk', response=AttendanceDeskOut)
def attendance_desk(request):
    visits = list_today_visits()
    inside = sum(1 for item in visits if item['is_inside'])
    checkouts = sum(1 for item in visits if not item['is_inside'])
    return {
        'date': timezone.localdate(),
        'checkins': len(visits),
        'inside': inside,
        'checkouts': checkouts,
        'by_class': class_headcount(visits),
        'visits': visits,
    }


@router.get('/fitness/attendance/lookup', response=AttendanceLookupOut)
def attendance_lookup(request, q: str = ''):
    exact, members = lookup_members(q)
    return {
        'query': q,
        'exact': exact,
        'matches': [desk_member(item) for item in members],
    }


@router.post('/fitness/attendance/check-in', response=AttendanceOut)
def check_in(request, payload: AttendanceIn):
    member = require_checkin_member(payload.member_id)
    existing = open_visit_today(member.id)
    if existing:
        raise HttpError(409, 'This member is already checked in')
    visit = Attendance.objects.create(member=member)
    create_gym_notifications('member_check_in', 'members', 'Member check-in', f'{member.user.get_full_name()} checked in.', member.id, request.user)
    return attendance_data(visit)


@router.post('/fitness/attendance/check-out', response=AttendanceOut)
def check_out(request, payload: AttendanceCheckOutIn):
    visit = None
    if payload.visit_id:
        visit = Attendance.objects.select_related('member__user').filter(
            id=payload.visit_id,
            checked_in_at__date=timezone.localdate(),
        ).first()
    elif payload.member_id:
        visit = open_visit_today(payload.member_id)
    if visit is None:
        raise HttpError(404, 'No open check-in found for this member')
    if visit.checked_out_at:
        raise HttpError(400, 'This visit is already checked out')
    visit.checked_out_at = timezone.now()
    visit.save(update_fields=['checked_out_at', 'updated_at'])
    return attendance_data(visit)


@router.get('/fitness/members/{member_id}/qr')
def member_qr(request, member_id: int):
    return qr_response(member_id)


@router.get('/fitness/trainers', response=List[TrainerOut])
def list_trainers(request, year: Optional[int] = None, month: Optional[int] = None):
    _require_gym_admin(request)
    year, month = _report_period(year, month)
    trainers = Trainer.objects.filter(is_active=True).prefetch_related('payrolls')
    payrolls = {
        item.trainer_id: item
        for item in TrainerPayroll.objects.filter(year=year, month=month, trainer__is_active=True)
    }
    return [trainer_data(trainer, year, month, payrolls.get(trainer.id)) for trainer in trainers]


@router.post('/fitness/trainers', response=TrainerOut)
def create_trainer(request, payload: TrainerIn):
    _require_gym_admin(request)
    year, month = _report_period(None, None)
    trainer = Trainer.objects.create(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        specialization=payload.specialization.strip(),
        phone=payload.phone.strip(),
        monthly_pay=payload.monthly_pay,
        is_active=payload.is_active,
    )
    payroll = None
    if payload.monthly_pay or payload.pay_amount is not None or payload.is_paid:
        payroll = _upsert_trainer_payroll(
            trainer,
            year,
            month,
            pay_amount=payload.pay_amount,
            is_paid=payload.is_paid,
        )
    create_gym_notifications(
        'important_system_alerts',
        'system',
        'Trainer added',
        f'{trainer.name} was added to the coaching team.',
        actor=request.user,
        admin_only=True,
    )
    return trainer_data(trainer, year, month, payroll)


@router.put('/fitness/trainers/{trainer_id}', response=TrainerOut)
def update_trainer(request, trainer_id: int, payload: TrainerIn):
    _require_gym_admin(request)
    year, month = _report_period(None, None)
    try:
        trainer = Trainer.objects.get(id=trainer_id)
    except Trainer.DoesNotExist:
        raise HttpError(404, 'Trainer not found')
    trainer.first_name = payload.first_name.strip()
    trainer.last_name = payload.last_name.strip()
    trainer.specialization = payload.specialization.strip()
    trainer.phone = payload.phone.strip()
    trainer.monthly_pay = payload.monthly_pay
    trainer.is_active = payload.is_active
    trainer.save()
    payroll = None
    if payload.pay_amount is not None or payload.is_paid:
        payroll = _upsert_trainer_payroll(
            trainer,
            year,
            month,
            pay_amount=payload.pay_amount,
            is_paid=payload.is_paid,
        )
    return trainer_data(trainer, year, month, payroll)


@router.patch('/fitness/trainers/{trainer_id}/payroll', response=TrainerOut)
def update_trainer_payroll(request, trainer_id: int, payload: TrainerPayrollIn):
    _require_gym_admin(request)
    year, month = _report_period(payload.year, payload.month)
    try:
        trainer = Trainer.objects.get(id=trainer_id)
    except Trainer.DoesNotExist:
        raise HttpError(404, 'Trainer not found')
    payroll = _upsert_trainer_payroll(
        trainer,
        year,
        month,
        pay_amount=payload.pay_amount,
        is_paid=payload.is_paid,
        notes=payload.notes,
    )
    status_text = 'paid' if payroll.is_paid else 'unpaid'
    create_gym_notifications(
        'important_system_alerts',
        'system',
        'Trainer payroll updated',
        f'{trainer.name} is {status_text} for {month_name[month]} {year} ({payroll.pay_amount} MAD).',
        actor=request.user,
        admin_only=True,
    )
    return trainer_data(trainer, year, month, payroll)


@router.delete('/fitness/trainers/{trainer_id}')
def delete_trainer(request, trainer_id: int):
    _require_gym_admin(request)
    try:
        trainer = Trainer.objects.get(id=trainer_id, is_active=True)
    except Trainer.DoesNotExist:
        raise HttpError(404, 'Trainer not found')
    name = trainer.name
    trainer.is_active = False
    trainer.save(update_fields=['is_active', 'updated_at'])
    create_gym_notifications(
        'important_system_alerts',
        'system',
        'Trainer removed',
        f'{name} was removed from the coaching team.',
        actor=request.user,
        admin_only=True,
    )
    return {'success': True}


def _expense_data(item):
    return {
        'id': item.id,
        'category': item.category,
        'category_label': item.get_category_display(),
        'title': item.title,
        'amount': item.amount,
        'year': item.year,
        'month': item.month,
        'notes': item.notes,
    }


@router.get('/fitness/expenses', response=List[GymExpenseOut])
def list_expenses(request, year: Optional[int] = None, month: Optional[int] = None):
    _require_gym_admin(request)
    year, month = _report_period(year, month)
    return [_expense_data(item) for item in GymExpense.objects.filter(year=year, month=month)]


@router.post('/fitness/expenses', response=GymExpenseOut)
def create_expense(request, payload: GymExpenseIn):
    _require_gym_admin(request)
    year, month = _report_period(payload.year, payload.month)
    if payload.category not in ExpenseCategory.values:
        raise HttpError(400, 'Invalid expense category')
    title = payload.title.strip() or dict(ExpenseCategory.choices).get(payload.category, payload.category)
    expense = GymExpense.objects.create(
        category=payload.category,
        title=title,
        amount=payload.amount,
        year=year,
        month=month,
        notes=(payload.notes or '').strip(),
    )
    create_gym_notifications(
        'important_system_alerts',
        'system',
        'Expense recorded',
        f'{expense.get_category_display()}: {expense.amount} MAD for {month_name[month]} {year}.',
        actor=request.user,
        admin_only=True,
    )
    return _expense_data(expense)


@router.delete('/fitness/expenses/{expense_id}')
def delete_expense(request, expense_id: int):
    _require_gym_admin(request)
    try:
        expense = GymExpense.objects.get(id=expense_id)
    except GymExpense.DoesNotExist:
        raise HttpError(404, 'Expense not found')
    expense.delete()
    return {'success': True}


@router.get('/fitness/reports/overview', response=MonthlyOverviewOut)
def monthly_overview(request, year: Optional[int] = None, month: Optional[int] = None):
    _require_gym_admin(request)
    year, month = _report_period(year, month)
    income = class_revenue_report(request, year, month)
    trainers = trainer_payroll_report(request, year, month)
    expenses = list(GymExpense.objects.filter(year=year, month=month))
    zero = Decimal('0.00')
    operating_total = sum((item.amount for item in expenses), zero)
    category_totals = {}
    for item in expenses:
        bucket = category_totals.setdefault(item.category, {
            'category': item.category,
            'category_label': item.get_category_display(),
            'total': zero,
            'count': 0,
        })
        bucket['total'] += item.amount
        bucket['count'] += 1
    categories = sorted(category_totals.values(), key=lambda row: (-row['total'], row['category_label']))
    trainer_due = trainers['total_due']
    trainer_paid = trainers['total_paid']
    total_spend = operating_total + trainer_due
    collected = income['total_collected']
    return {
        'year': year,
        'month': month,
        'label': income['label'],
        'collected': collected,
        'expected': income['total_expected'],
        'outstanding': income['total_outstanding'],
        'operating_total': operating_total,
        'trainer_due': trainer_due,
        'trainer_paid': trainer_paid,
        'total_spend': total_spend,
        'net': collected - total_spend,
        'categories': categories,
        'expenses': [_expense_data(item) for item in expenses],
    }


def _monthly_export_payload(request, year: Optional[int], month: Optional[int]):
    overview = monthly_overview(request, year, month)
    income = class_revenue_report(request, year, month)
    trainers = trainer_payroll_report(request, year, month)
    return overview, income, trainers


@router.get('/fitness/reports/export/xlsx')
def export_monthly_xlsx(request, year: Optional[int] = None, month: Optional[int] = None):
    overview, income, trainers = _monthly_export_payload(request, year, month)
    return monthly_xlsx_response(overview, income, trainers)


@router.get('/fitness/reports/export/pdf')
def export_monthly_pdf(request, year: Optional[int] = None, month: Optional[int] = None):
    overview, income, trainers = _monthly_export_payload(request, year, month)
    return monthly_pdf_response(overview, income, trainers)


@router.get('/fitness/reports/trainers', response=TrainerPayrollReportOut)
def trainer_payroll_report(request, year: Optional[int] = None, month: Optional[int] = None):
    _require_gym_admin(request)
    year, month = _report_period(year, month)
    zero = Decimal('0.00')
    payrolls = {
        item.trainer_id: item
        for item in TrainerPayroll.objects.filter(year=year, month=month).select_related('trainer')
    }
    rows = []
    for trainer in Trainer.objects.filter(is_active=True):
        payroll = payrolls.get(trainer.id)
        rows.append({
            'id': trainer.id,
            'name': trainer.name,
            'specialization': trainer.specialization,
            'monthly_pay': trainer.monthly_pay,
            'pay_amount': payroll.pay_amount if payroll else trainer.monthly_pay,
            'is_paid': payroll.is_paid if payroll else False,
        })
    total_due = sum((item['pay_amount'] for item in rows), zero)
    total_paid = sum((item['pay_amount'] for item in rows if item['is_paid']), zero)
    total_unpaid = total_due - total_paid
    return {
        'year': year,
        'month': month,
        'label': f'{month_name[month]} {year}',
        'total_due': total_due,
        'total_paid': total_paid,
        'total_unpaid': total_unpaid,
        'paid_count': sum(1 for item in rows if item['is_paid']),
        'unpaid_count': sum(1 for item in rows if not item['is_paid'] and item['pay_amount'] > 0),
        'trainers': rows,
    }
