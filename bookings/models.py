from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import BaseModel
from users.models import ClientProfile, ProviderProfile, Property


class BookingStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"
    REJECTED = "rejected", "Rejected"
    EXPIRED = "expired", "Expired"


class PaymentStatus(models.TextChoices):
    UNPAID = "unpaid", "Unpaid"
    PARTIAL = "partial", "Partially Paid"
    PAID = "paid", "Paid"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"


class Booking(BaseModel):
    """Monthly property booking with a frozen price snapshot."""

    client = models.ForeignKey(
        ClientProfile, on_delete=models.PROTECT, related_name="bookings"
    )
    provider = models.ForeignKey(
        ProviderProfile, on_delete=models.PROTECT, related_name="bookings"
    )
    property_ref = models.ForeignKey(
        Property, on_delete=models.PROTECT, related_name="bookings"
    )

    start_date = models.DateField()
    end_date = models.DateField()

    monthly_price = models.DecimalField(max_digits=15, decimal_places=2)
    number_of_months = models.IntegerField(default=1)
    total_price = models.DecimalField(max_digits=15, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )

    notes = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"
        indexes = [
            models.Index(fields=["status", "payment_status"], name="bookings_bo_status_92d418_idx"),
            models.Index(fields=["client", "status"], name="bookings_bo_client__09b1d6_idx"),
            models.Index(fields=["provider", "status"], name="bookings_bo_provide_status_idx"),
            models.Index(
                fields=["property_ref", "start_date", "end_date"],
                name="bookings_bo_propert_41c841_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Booking #{self.id} - {self.client.user.first_name} "
            f"({self.start_date} to {self.end_date})"
        )

    @property
    def total_paid(self) -> Decimal:
        return self.payments.filter(status=PaymentStatus.PAID).aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0.00")

    @property
    def remaining_balance(self) -> Decimal:
        return self.total_price - self.total_paid


class BookingPayment(BaseModel):
    """Cash payment recorded against a booking."""

    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PAID,
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_booking_payments",
    )
    received_by_user = models.CharField(
        max_length=200, help_text="Name of staff who received payment"
    )
    received_at = models.DateTimeField(auto_now_add=True)
    receipt_number = models.CharField(max_length=50, unique=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]
        verbose_name = "Booking Payment"
        verbose_name_plural = "Booking Payments"
        indexes = [
            models.Index(fields=["booking", "status"], name="bookings_bo_booking_7d458c_idx"),
        ]

    def __str__(self):
        return f"Payment {self.id} - {self.amount} MAD for Booking #{self.booking_id}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            stamp = timezone.now().strftime("%Y%m%d%H%M%S")
            self.receipt_number = f"HZ-{stamp}-{uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
        self._refresh_booking_payment_status()

    def _refresh_booking_payment_status(self):
        booking = self.booking
        total_paid = booking.total_paid
        if total_paid >= booking.total_price:
            booking.payment_status = PaymentStatus.PAID
        elif total_paid > 0:
            booking.payment_status = PaymentStatus.PARTIAL
        else:
            booking.payment_status = PaymentStatus.UNPAID
        booking.save(update_fields=["payment_status", "updated_at"])
