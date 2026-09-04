from django.core.management.base import BaseCommand

from bookings.services import update_booking_statuses


class Command(BaseCommand):
    help = "Updates booking statuses based on current date (APPROVED→ACTIVE, ACTIVE→COMPLETED)"

    def handle(self, *args, **options):
        result = update_booking_statuses()
        self.stdout.write(
            self.style.SUCCESS(
                "Successfully updated booking statuses "
                f"(activated={result['activated']}, completed={result['completed']})"
            )
        )
