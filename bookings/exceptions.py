"""Domain errors mapped to clean API responses."""


class BookingError(Exception):
    status_code = 400
    default_message = "A booking error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class InvalidBookingDates(BookingError):
    default_message = "Invalid booking dates."


class PropertyUnavailable(BookingError):
    default_message = "Property is already booked for these dates."


class InvalidProperty(BookingError):
    default_message = "Invalid property."


class InvalidClient(BookingError):
    default_message = "Invalid client."


class BookingNotFound(BookingError):
    status_code = 404
    default_message = "Booking not found."


class InvalidStatusTransition(BookingError):
    default_message = "This booking status change is not allowed."


class BookingCannotBeCancelled(BookingError):
    default_message = "Booking cannot be cancelled because it has already been completed."


class PaymentExceedsBalance(BookingError):
    default_message = "Payment amount exceeds remaining balance."


class InvalidPaymentAmount(BookingError):
    default_message = "Payment amount must be greater than 0."


class DuplicatePayment(BookingError):
    default_message = "A payment with this receipt number already exists."


class PermissionDenied(BookingError):
    status_code = 403
    default_message = "You do not have permission to modify this booking."
