from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from movies.models import Seat, Booking


class Command(BaseCommand):
    help = "Release seats reserved for more than 2 minutes"

    def handle(self, *args, **options):
        expiry_time = timezone.now() - timezone.timedelta(minutes=2)

        expired_seats = Seat.objects.filter(
            reserved_at__lt=expiry_time,
            bookings__status='pending'
        ).distinct()

        released_count = 0

        for seat in expired_seats:
            with transaction.atomic():
                seat = Seat.objects.select_for_update().get(id=seat.id)

                if seat.reserved_at and seat.reserved_at < expiry_time:
                    Booking.objects.filter(
                        seat=seat,
                        status='pending'
                    ).update(status='cancelled')

                    seat.reserved_by = None
                    seat.reserved_at = None
                    seat.save()

                    released_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Released {released_count} expired seat(s)."
            )
        )