from django.contrib import admin

from fitness.models import Attendance, ClassMember, ClassSchedule, GymExpense, GymPayment, Membership, MembershipPlan, Trainer, TrainerPayroll, TrainingClass


class ClassMemberInline(admin.TabularInline):
    model = ClassMember
    extra = 0
    readonly_fields = ('joined_at',)


class ClassScheduleInline(admin.TabularInline):
    model = ClassSchedule
    extra = 0
    autocomplete_fields = ('trainer',)
    fields = ('weekday', 'start_time', 'end_time', 'trainer', 'location', 'capacity', 'is_active')


@admin.register(TrainingClass)
class TrainingClassAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'class_type', 'price_per_member', 'member_count_display',
        'team_total_display', 'is_active',
    )
    list_filter = ('class_type', 'is_active')
    search_fields = ('name', 'members__client__user__first_name', 'members__client__user__last_name')
    readonly_fields = ('member_count_display', 'team_total_display', 'created_at', 'updated_at')
    inlines = (ClassMemberInline, ClassScheduleInline,)
    fieldsets = (
        ('Class', {'fields': ('name', 'class_type', 'is_active')}),
        ('Pricing', {'fields': ('price_per_member', 'member_count_display', 'team_total_display')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Members')
    def member_count_display(self, obj):
        return obj.member_count

    @admin.display(description='Team total (MAD)')
    def team_total_display(self, obj):
        return f'{obj.team_total:.2f} MAD'


@admin.register(ClassSchedule)
class ClassScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'training_class', 'weekday', 'start_time', 'end_time',
        'trainer', 'location', 'capacity', 'is_active',
    )
    list_filter = ('weekday', 'is_active', 'training_class')
    search_fields = ('training_class__name', 'location', 'trainer__first_name', 'trainer__last_name')
    autocomplete_fields = ('training_class', 'trainer')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ClassMember)
class ClassMemberAdmin(admin.ModelAdmin):
    list_display = ('training_class', 'client', 'joined_at', 'is_active')
    list_filter = ('training_class', 'is_active', 'joined_at')
    search_fields = ('training_class__name', 'client__user__first_name', 'client__user__last_name')
    readonly_fields = ('joined_at', 'created_at', 'updated_at')


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_months', 'price', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('member', 'plan', 'start_date', 'end_date', 'price', 'status_display', 'payment_status')
    list_filter = ('status_override', 'plan')
    search_fields = ('member__user__first_name', 'member__user__last_name', 'member__phone')
    readonly_fields = ('status_display', 'payment_status', 'total_paid', 'remaining_balance', 'created_at', 'updated_at')

    @admin.display(description='Status')
    def status_display(self, obj):
        return obj.status


@admin.register(GymPayment)
class GymPaymentAdmin(admin.ModelAdmin):
    list_display = ('membership', 'amount', 'payment_method', 'received_by', 'received_at')
    list_filter = ('payment_method', 'received_at')
    search_fields = ('membership__member__user__first_name', 'membership__member__user__last_name', 'received_by')
    readonly_fields = ('received_at', 'created_at', 'updated_at')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('member', 'checked_in_at', 'checked_out_at')
    list_filter = ('checked_in_at',)
    search_fields = ('member__user__first_name', 'member__user__last_name')
    readonly_fields = ('checked_in_at', 'created_at', 'updated_at')


class TrainerPayrollInline(admin.TabularInline):
    model = TrainerPayroll
    extra = 0
    fields = ('year', 'month', 'pay_amount', 'is_paid', 'paid_at', 'notes')
    readonly_fields = ('paid_at',)


@admin.register(GymExpense)
class GymExpenseAdmin(admin.ModelAdmin):
    list_display = ('category', 'title', 'amount', 'month', 'year', 'created_at')
    list_filter = ('category', 'year', 'month')
    search_fields = ('title', 'notes')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'specialization', 'monthly_pay', 'phone', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('first_name', 'last_name', 'specialization', 'phone')
    inlines = (TrainerPayrollInline,)
