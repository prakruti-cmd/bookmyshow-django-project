from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings
from .models import Booking

from io import BytesIO
import qrcode

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3
)
def generate_and_send_ticket(self, booking_id):

    booking = Booking.objects.select_related(
        'user',
        'movie',
        'theater',
        'seat'
    ).get(id=booking_id)

    # Create QR code
    qr_data = (
        f"Booking ID: {booking.id}\n"
        f"Payment Reference: {booking.payment_reference}"
    )

    qr = qrcode.make(qr_data)

    qr_buffer = BytesIO()
    qr.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)

    # Create PDF
    pdf_buffer = BytesIO()

    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    elements = []

    elements.append(
        Paragraph(
            "BOOKMYSEAT - MOVIE TICKET",
            styles['Title']
        )
    )

    elements.append(Spacer(1, 20))

    ticket_details = [
        ["Booking ID", str(booking.id)],
        ["Movie", booking.movie.name],
        ["Theater", booking.theater.name],
        ["Screen", booking.theater.screen],
        ["Show Timing", str(booking.theater.time)],
        ["Booked Seat", booking.seat.seat_number],
        ["Payment Reference", booking.payment_reference],
        ["User", booking.user.username],
    ]

    table = Table(ticket_details, colWidths=[150, 330])

    table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
        ])
    )

    elements.append(table)

    elements.append(Spacer(1, 25))

    qr_image = Image(qr_buffer, width=1.5 * inch, height=1.5 * inch)

    elements.append(qr_image)

    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            "Scan the QR code to verify this booking.",
            styles['Normal']
        )
    )

    document.build(elements)

    pdf_buffer.seek(0)

    # Send email
    email = EmailMessage(
        subject=f"Your Movie Ticket - Booking #{booking.id}",
        body=(
            f"Hello {booking.user.username},\n\n"
            f"Your movie booking was successful.\n"
            f"Your ticket is attached to this email.\n\n"
            f"Booking ID: {booking.id}\n"
            f"Movie: {booking.movie.name}\n\n"
            f"Thank you for using BookMySeat."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL
        if hasattr(settings, 'DEFAULT_FROM_EMAIL')
        else 'noreply@bookmyseat.com',
        to=[booking.user.email]
    )

    email.attach(
        f"ticket_{booking.id}.pdf",
        pdf_buffer.getvalue(),
        'application/pdf'
    )

    email.send()
    
@shared_task
def release_expired_seats():
    from django.utils import timezone
    from django.db import transaction
    from .models import Seat, Booking

    expiry_time = timezone.now() - timezone.timedelta(minutes=2)

    expired_seats = Seat.objects.filter(
        reserved_at__lt=expiry_time,
        bookings__status='pending'
    ).distinct()

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