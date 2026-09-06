from datetime import date
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.conf import settings

from core.models import BaseModel
from users.models import ClientProfile


class GymNotificationSettings(BaseModel):
    membership_expiring_soon = models.BooleanField(default=True)
    membership_expired = models.BooleanField(default=True)
    outstanding_payment = models.BooleanField(default=True)
    new_member_registered = models.BooleanField(default=True)
    payment_received = models.BooleanField(default=True)
    important_system_alerts = models.BooleanField(default=True)
    new_membership_created = models.BooleanField(default=True)
    membership_renewed = models.BooleanField(default=True)
    partial_payment = models.BooleanField(default=True)
    member_updated = models.BooleanField(default=True)
    member_deactivated = models.BooleanField(default=True)
    member_check_in = models.BooleanField(default=True)
    new_staff_user_created = models.BooleanField(default=True)
    user_role_changed = models.BooleanField(default=True)
    user_deactivated = models.BooleanField(default=True)

    def __str__(self):
        return 'Gym notification settings'


class GymNotification(BaseModel):
    CATEGORY_CHOICES = [('memberships', 'Memberships'), ('payments', 'Payments'), ('members', 'Members'), ('system', 'System')]
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='gym_notifications')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=180)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    member_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']


class FitnessClassType(models.TextChoices):
    BOXING = 'boxing', 'Boxing'
    MUSCULATION = 'musculation', 'Musculation'
    AEROBIC = 'aerobic', 'Aerobic'
    KICK_BOXING = 'kick_boxing', 'Kick Boxing'


class TrainingClass(BaseModel):
    """A fitness class with a team of registered clients."""

    name = models.CharField(max_length=150)
    class_type = models.CharField(max_length=30, choices=FitnessClassType.choices)
    price_per_member = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Monthly price per team member in MAD (DH).',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['class_type', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'class_type'],
                name='unique_fitness_class_name_and_type',
            ),
        ]

    def __str__(self):
        return f'{self.name} - {self.get_class_type_display()}'

    @property
    def member_count(self):
        return self.members.filter(is_active=True, client__is_active=True).count()

    @property
    def team_total(self):
        """Total price for the team, calculated from its current members."""
        return self.price_per_member * self.member_count


class ClassMember(BaseModel):
    """A client registered in a training class team."""

    training_class = models.ForeignKey(
        TrainingClass,
        on_delete=models.CASCADE,
        related_name='members',
    )
    client = models.ForeignKey(
        ClientProfile,
        on_delete=models.PROTECT,
        related_name='fitness_memberships',
    )
    joined_at = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['client__user__first_name', 'client__user__last_name']
        constraints = [
            models.UniqueConstraint(
                fields=['training_class', 'client'],
                name='unique_client_per_fitness_class',
            ),
        ]

    def __str__(self):
        return f'{self.client} - {self.training_class}'


class MembershipPlan(BaseModel):
    name = models.CharField(max_length=120, unique=True)
    duration_months = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['duration_months', 'name']

    def __str__(self):
        return f'{self.name} ({self.price} MAD)'


class MembershipStatus(models.TextChoices):
    CANCELLED = 'cancelled', 'Cancelled'
    SUSPENDED = 'suspended', 'Suspended'


class PaymentStatusOverride(models.TextChoices):
    PAID = 'paid', 'Paid'
    UNPAID = 'unpaid', 'Unpaid'


class Membership(BaseModel):
    member = models.ForeignKey(ClientProfile, on_delete=models.PROTECT, related_name='gym_memberships')
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name='memberships')
    start_date = models.DateField()
    end_date = models.DateField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    status_override = models.CharField(max_length=20, choices=MembershipStatus.choices, blank=True)
    payment_status_override = models.CharField(max_length=20, choices=PaymentStatusOverride.choices, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']
        indexes = [models.Index(fields=['member', 'end_date']), models.Index(fields=['end_date', 'status_override'])]

    @property
    def status(self):
        if self.status_override:
            return self.status_override
        today = date.today()
        if self.end_date < today:
            return 'expired'
        if self.start_date <= today <= self.end_date:
            return 'expiring_soon' if (self.end_date - today).days <= 7 else 'active'
        return 'upcoming'

    @property
    def total_paid(self):
        return self.payments.filter(status='paid').aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    @property
    def remaining_balance(self):
        return max(self.price - self.total_paid, Decimal('0.00'))

    @property
    def payment_status(self):
        if self.payment_status_override:
            return self.payment_status_override
        if self.total_paid >= self.price:
            return 'paid'
        if self.total_paid > 0:
            return 'partial'
        return 'unpaid'


class GymPayment(BaseModel):
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    status = models.CharField(max_length=20, default='paid')
    payment_method = models.CharField(max_length=20, default='cash')
    received_by = models.CharField(max_length=160)
    received_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['membership', 'status']),
            models.Index(fields=['received_at']),
        ]


class Attendance(BaseModel):
    member = models.ForeignKey(ClientProfile, on_delete=models.PROTECT, related_name='gym_attendance')
    checked_in_at = models.DateTimeField(auto_now_add=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-checked_in_at']


class Trainer(BaseModel):
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    specialization = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    monthly_pay = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Monthly pay in MAD (DH).',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def name(self):
        return f'{self.first_name} {self.last_name}'.strip()


class Weekday(models.IntegerChoices):
    MONDAY = 0, 'Monday'
    TUESDAY = 1, 'Tuesday'
    WEDNESDAY = 2, 'Wednesday'
    THURSDAY = 3, 'Thursday'
    FRIDAY = 4, 'Friday'
    SATURDAY = 5, 'Saturday'
    SUNDAY = 6, 'Sunday'


class ClassSchedule(BaseModel):
    """Weekly recurring slot for a training class. Not a single dated session row."""

    training_class = models.ForeignKey(
        TrainingClass,
        on_delete=models.CASCADE,
        related_name='schedules',
    )
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    trainer = models.ForeignKey(
        Trainer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_schedules',
    )
    location = models.CharField(max_length=150, blank=True)
    group = models.CharField(
        max_length=80,
        blank=True,
        default='',
        help_text='Optional calendar name for this weekly slot, for example boxing-kids.',
    )
    color = models.CharField(
        max_length=7,
        blank=True,
        default='',
        help_text='Optional calendar color as #RRGGBB.',
    )
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text='Optional maximum places for this slot. Separate from class roster size.',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['weekday', 'start_time', 'training_class__name']
        indexes = [
            models.Index(fields=['weekday', 'is_active']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F('start_time')),
                name='class_schedule_end_after_start',
            ),
        ]

    def __str__(self):
        return f'{self.training_class} {self.get_weekday_display()} {self.start_time}-{self.end_time}'


class TrainerPayroll(BaseModel):
    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE, related_name='payrolls')
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    hours_worked = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    pay_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-year', '-month', 'trainer__first_name']
        constraints = [
            models.UniqueConstraint(fields=['trainer', 'year', 'month'], name='unique_trainer_payroll_month'),
        ]

    def __str__(self):
        return f'{self.trainer} {self.month}/{self.year}'


class ExpenseCategory(models.TextChoices):
    ELECTRICITY = 'electricity', 'Electricity'
    WATER = 'water', 'Water'
    INTERNET = 'internet', 'Internet'
    RENT = 'rent', 'Rent'
    CLEANING = 'cleaning', 'Cleaning'
    SUPPLIES = 'supplies', 'Supplies'
    MAINTENANCE = 'maintenance', 'Maintenance'
    OTHER = 'other', 'Other'


class GymExpense(BaseModel):
    category = models.CharField(max_length=30, choices=ExpenseCategory.choices, default=ExpenseCategory.OTHER)
    title = models.CharField(max_length=180, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-year', '-month', 'category', '-created_at']

    def __str__(self):
        return f'{self.get_category_display()} {self.amount} ({self.month}/{self.year})'


class GymWhatsAppReminder(BaseModel):
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name='whatsapp_reminders')
    kind = models.CharField(max_length=40)
    message = models.TextField(blank=True)
    sent_by = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.membership_id} {self.kind}'
