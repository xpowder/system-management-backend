from django.contrib import admin

from bookings.models import Booking, BookingPayment


class BookingPaymentInline(admin.TabularInline):
    model = BookingPayment
    extra = 0
    can_delete = False
    readonly_fields = ("received_at", "created_at", "updated_at", "receipt_number")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "get_client_name",
        "property_ref",
        "start_date",
        "end_date",
        "total_price",
        "status",
        "payment_status",
        "created_at",
    )
    list_filter = ("status", "payment_status", "payment_method", "created_at", "start_date")
    search_fields = (
        "id",
        "client__user__first_name",
        "client__user__last_name",
        "client__phone",
        "property_ref__name",
        "provider__user__first_name",
        "provider__company_name",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "monthly_price",
        "number_of_months",
        "total_price",
        "total_paid_display",
        "remaining_balance_display",
    )
    date_hierarchy = "start_date"
    inlines = [BookingPaymentInline]
    fieldsets = (
        ("Booking Information", {"fields": ("client", "provider", "property_ref")}),
        ("Dates", {"fields": ("start_date", "end_date")}),
        (
            "Pricing",
            {
                "fields": (
                    "monthly_price",
                    "number_of_months",
                    "total_price",
                    "total_paid_display",
                    "remaining_balance_display",
                )
            },
        ),
        ("Status", {"fields": ("status", "payment_status", "payment_method")}),
        (
            "Notes & Tracking",
            {"fields": ("notes", "approved_at", "cancelled_at", "completed_at")},
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Client")
    def get_client_name(self, obj):
        return f"{obj.client.user.first_name} {obj.client.user.last_name}"

    @admin.display(description="Total paid (MAD)")
    def total_paid_display(self, obj):
        return obj.total_paid

    @admin.display(description="Remaining (MAD)")
    def remaining_balance_display(self, obj):
        return obj.remaining_balance


@admin.register(BookingPayment)
class BookingPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "booking",
        "get_client_name",
        "amount",
        "status",
        "payment_method",
        "received_by_user",
        "received_at",
        "receipt_number",
    )
    list_filter = ("status", "payment_method", "received_at")
    search_fields = (
        "booking__id",
        "booking__client__user__first_name",
        "booking__client__user__last_name",
        "received_by_user",
        "receipt_number",
    )
    readonly_fields = ("created_at", "updated_at", "received_at")
    date_hierarchy = "received_at"

    @admin.display(description="Client")
    def get_client_name(self, obj):
        return f"{obj.booking.client.user.first_name} {obj.booking.client.user.last_name}"
