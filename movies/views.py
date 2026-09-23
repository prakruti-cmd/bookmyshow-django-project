from django.shortcuts import render, redirect, get_object_or_404
import uuid
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from .models import Movie, Theater, Seat, Booking, Review, Payment
from .tasks import generate_and_send_ticket
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.utils import timezone
from urllib.parse import urlparse, parse_qs
import razorpay
from django.conf import settings
import json
from django.views.decorators.csrf import csrf_exempt


# =========================================================
# RELEASE EXPIRED RESERVATIONS
# =========================================================

def release_expired_reservations():
    expiry_time = timezone.now() - timezone.timedelta(minutes=2)

    expired_seats = Seat.objects.filter(
        reserved_at__lt=expiry_time,
        bookings__status='pending'
    ).distinct()

    for seat in expired_seats:
        with transaction.atomic():
            seat = Seat.objects.select_for_update().get(id=seat.id)

            if seat.reserved_at and seat.reserved_at < expiry_time:
                expired_bookings = Booking.objects.filter(
                    seat=seat,
                    status='pending'
                )

                expired_bookings.update(
                    status='cancelled'
                )

                Payment.objects.filter(
                    booking__in=expired_bookings,
                    status='pending'
                ).update(
                    status='cancelled'
                )
                seat.reserved_by = None
                seat.reserved_at = None
                seat.save()


# =========================================================
# RAZORPAY CLIENT
# =========================================================

razorpay_client = razorpay.Client(
    auth=(
        settings.RAZORPAY_KEY_ID,
        settings.RAZORPAY_KEY_SECRET
    )
)

# =========================================================
# MOVIE LIST
# =========================================================

def movie_list(request):

    trending_movies = Movie.objects.order_by('-popularity')[:5]
    recently_released = Movie.objects.order_by('-release_date')[:5]

    search_query = request.GET.get('search')

    if search_query:
        movies = Movie.objects.filter(
            name__icontains=search_query
        )
    else:
        movies = Movie.objects.all()

    genre = request.GET.get('genre')

    if genre:
        movies = movies.filter(genre=genre)

    language = request.GET.get('language')

    if language:
        movies = movies.filter(language=language)

    city = request.GET.get('city')

    if city:
        movies = movies.filter(city=city)

    theater = request.GET.get('theater')

    if theater:
        movies = movies.filter(
            theaters__name=theater
        )

    release_date = request.GET.get('release_date')

    if release_date:
        movies = movies.filter(
            release_date=release_date
        )

    show_time = request.GET.get('show_time')

    if show_time == 'morning':
        movies = movies.filter(
            theaters__time__hour__gte=6,
            theaters__time__hour__lt=12
        )

    elif show_time == 'afternoon':
        movies = movies.filter(
            theaters__time__hour__gte=12,
            theaters__time__hour__lt=17
        )

    elif show_time == 'evening':
        movies = movies.filter(
            theaters__time__hour__gte=17,
            theaters__time__hour__lt=21
        )

    elif show_time == 'night':
        movies = movies.filter(
            theaters__time__hour__gte=21,
            theaters__time__hour__lt=24
        )

    movies = movies.distinct()

    rating = request.GET.get('rating')

    if rating:
        movies = movies.filter(
            rating__gte=rating
        )

    movies = movies.distinct()

    sort = request.GET.get('sort')

    if sort == 'popularity':
        movies = movies.order_by('-popularity')

    elif sort == 'newest':
        movies = movies.order_by('-release_date')

    elif sort == 'rating':
        movies = movies.order_by('-rating')

    elif sort == 'price_low':
        movies = movies.order_by('ticket_price')

    elif sort == 'price_high':
        movies = movies.order_by('-ticket_price')

    movie_count = movies.count()

    paginator = Paginator(movies, 6)

    page_number = request.GET.get('page')

    movies = paginator.get_page(page_number)

    recommended_movies = Movie.objects.none()

    if request.user.is_authenticated:

        booked_movies = Booking.objects.filter(
            user=request.user
        ).values_list(
            'movie_id',
            flat=True
        )

        recently_viewed = request.session.get(
            'recently_viewed',
            []
        )

        movie_ids = list(booked_movies) + recently_viewed

        if movie_ids:

            preferred_genres = Movie.objects.filter(
                id__in=movie_ids
            ).values_list(
                'genre',
                flat=True
            )

            recently_viewed_movies = Movie.objects.filter(
                id__in=recently_viewed
            ).exclude(
                id__in=booked_movies
            ).order_by('-release_date')

            genre_recommendations = Movie.objects.filter(
                genre__in=preferred_genres
            ).exclude(
                id__in=booked_movies
            ).exclude(
                id__in=recently_viewed
            ).order_by('-release_date').distinct()

            recommended_movies = list(
                recently_viewed_movies[:5]
            )

            remaining = 5 - len(
                recommended_movies
            )

            if remaining > 0:
                recommended_movies += list(
                    genre_recommendations[:remaining]
                )
    return render(
        request,
        'movies/movie_list.html',
        {
            'movies': movies,
            'trending_movies': trending_movies,
            'recently_released': recently_released,
            'recommended_movies': recommended_movies,
            'movie_count': movie_count,
        }
    )


# =========================================================
# THEATER LIST
# =========================================================

def theater_list(request, movie_id):

    movie = get_object_or_404(
        Movie,
        id=movie_id
    )

    theater = Theater.objects.filter(
        movie=movie
    )

    recently_viewed = request.session.get(
        'recently_viewed',
        []
    )

    if movie_id not in recently_viewed:
        recently_viewed.append(movie_id)

    request.session['recently_viewed'] = recently_viewed[-5:]

    return render(
        request,
        'movies/theater_list.html',
        {
            'movie': movie,
            'theaters': theater
        }
    )


# =========================================================
# BOOK SEATS
# =========================================================

@login_required(login_url='/login/')
def book_seats(request, theater_id):

    release_expired_reservations()

    theaters = get_object_or_404(
        Theater,
        id=theater_id
    )

    seats = Seat.objects.filter(
        theater=theaters
    )

    if request.method == 'POST':

        selected_Seats = request.POST.getlist('seats')

        created_bookings = []

        if not selected_Seats:
            return render(
                request,
                'movies/seat_selection.html',
                {
                    'theaters': theaters,
                    'seats': seats,
                    'error': 'No seat selected'
                }
            )

        with transaction.atomic():

            locked_seats = []

            for seat_id in selected_Seats:

                seat = Seat.objects.select_for_update().get(
                    id=seat_id,
                    theater=theaters
                )

                locked_seats.append(seat)

            error_seats = []

            for seat in locked_seats:

                if seat.is_booked:
                    error_seats.append(
                        seat.seat_number
                    )
                    continue

                if Booking.objects.filter(
                    seat=seat,
                    status__in=[
                        'pending',
                        'confirmed'
                    ]
                ).exists():

                    error_seats.append(
                        seat.seat_number
                    )

            if error_seats:

                error_message = (
                    'The following seats are already booked: '
                    + ','.join(error_seats)
                )

                return render(
                    request,
                    'movies/seat_selection.html',
                    {
                        'theaters': theaters,
                        'seats': seats,
                        'error': error_message
                    }
                )

            for seat in locked_seats:

                seat.reserved_by = request.user
                seat.reserved_at = timezone.now()
                seat.save()

                booking = Booking.objects.create(
                    user=request.user,
                    seat=seat,
                    movie=theaters.movie,
                    theater=theaters,
                    payment_reference=(
                        f"PAY-{uuid.uuid4().hex[:12].upper()}"
                    ),
                    status='pending'
                )

                Payment.objects.create(
                    booking=booking,
                    transaction_id=(
                        f"TXN-{uuid.uuid4().hex[:12].upper()}"
                    ),
                    amount=theaters.movie.ticket_price,
                    status='pending'
                )

                created_bookings.append(
                    booking
                )

        total_amount = sum(
            booking.movie.ticket_price
            for booking in created_bookings
        )

        razorpay_order = razorpay_client.order.create({
            'amount': int(total_amount * 100),
            'currency': 'INR',
            'receipt': (
                f"booking_{created_bookings[0].id}"
            )
        })
        
        print("RAZORPAY ORDER:", razorpay_order)

        for booking in created_bookings:

            payment = Payment.objects.get(
                booking=booking
            )

            payment.razorpay_order_id = (
                razorpay_order['id']
            )

            payment.save()

        return redirect(
            'payment_page',
            booking_id=created_bookings[0].id
        )

    release_expired_reservations()

    return render(
        request,
        'movies/seat_selection.html',
        {
            'theaters': theaters,
            'seats': seats
        }
    )


# =========================================================
# PAYMENT PAGE
# =========================================================

@login_required(login_url='/login/')
def payment_page(request, booking_id):

    booking = get_object_or_404(
        Booking,
        id=booking_id,
        user=request.user
    )

    payment = Payment.objects.filter(
        booking=booking,
        status='pending'
    ).order_by(
        '-created_at'
    ).first()

    if not payment:
        return redirect('profile')

    pending_payments = Payment.objects.filter(
        razorpay_order_id=payment.razorpay_order_id,
        status='pending'
    )

    total_amount = sum(
        p.amount
        for p in pending_payments
    )

    return render(
        request,
        'movies/payment.html',
        {
            'booking': booking,
            'payment': payment,
            'razorpay_key_id': (
                settings.RAZORPAY_KEY_ID
            ),
            'razorpay_order_id': (
                payment.razorpay_order_id
            ),
            'razorpay_amount': int(
                total_amount * 100
            ),
        }
    )


# =========================================================
# RETRY PAYMENT
# =========================================================

@login_required(login_url='/login/')
def retry_payment(request, booking_id):

    booking = get_object_or_404(
        Booking,
        id=booking_id,
        user=request.user
    )

    if booking.status not in [
        'cancelled',
        'pending'
    ]:
        return redirect('profile')

    booking.status = 'pending'

    booking.seat.is_booked = False
    booking.seat.reserved_by = None
    booking.seat.reserved_at = None

    booking.seat.save()
    booking.save()

    payment = Payment.objects.create(
        booking=booking,
        transaction_id=(
            f"TXN-{uuid.uuid4().hex[:12].upper()}"
        ),
        amount=booking.movie.ticket_price,
        status='pending'
    )

    razorpay_order = razorpay_client.order.create({
        'amount': int(payment.amount * 100),
        'currency': 'INR',
        'receipt': (
            f"retry_booking_{booking.id}"
        )
    })

    payment.razorpay_order_id = (
        razorpay_order['id']
    )

    payment.save()

    return redirect(
        'payment_page',
        booking_id=booking.id
    )


# =========================================================
# DOWNLOAD TICKET
# =========================================================

@login_required(login_url='/login/')
def download_ticket(request, booking_id):

    booking = get_object_or_404(
        Booking,
        id=booking_id,
        user=request.user
    )

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
    from reportlab.lib.styles import (
        getSampleStyleSheet
    )
    from reportlab.lib.units import inch

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
            'BOOKMYSEAT - MOVIE TICKET',
            styles['Title']
        )
    )

    elements.append(
        Spacer(1, 20)
    )

    ticket_details = [
        ['Booking ID', str(booking.id)],
        ['Movie', booking.movie.name],
        ['Theater', booking.theater.name],
        ['Screen', booking.theater.screen],
        ['Show Timing', str(booking.theater.time)],
        ['Seat', booking.seat.seat_number],
        ['Payment Reference', booking.payment_reference],
        ['Booked By', booking.user.username],
    ]

    table = Table(
        ticket_details,
        colWidths=[150, 330]
    )

    table.setStyle(
        TableStyle([
            (
                'BACKGROUND',
                (0, 0),
                (0, -1),
                colors.lightgrey
            ),
            (
                'GRID',
                (0, 0),
                (-1, -1),
                1,
                colors.grey
            ),
            (
                'PADDING',
                (0, 0),
                (-1, -1),
                8
            ),
        ])
    )

    elements.append(table)

    elements.append(
        Spacer(1, 25)
    )

    qr_data = (
        f"Booking ID: {booking.id}\n"
        f"Payment Reference: "
        f"{booking.payment_reference}"
    )

    qr = qrcode.make(qr_data)

    qr_buffer = BytesIO()

    qr.save(
        qr_buffer,
        format='PNG'
    )

    qr_buffer.seek(0)

    qr_image = Image(
        qr_buffer,
        width=1.5 * inch,
        height=1.5 * inch
    )

    elements.append(qr_image)

    elements.append(
        Spacer(1, 10)
    )

    elements.append(
        Paragraph(
            'Scan the QR code to verify this booking.',
            styles['Normal']
        )
    )

    document.build(elements)

    pdf_buffer.seek(0)

    response = HttpResponse(
        pdf_buffer.getvalue(),
        content_type='application/pdf'
    )

    response['Content-Disposition'] = (
        f'attachment; filename="ticket_{booking.id}.pdf"'
    )

    return response


# =========================================================
# MOVIE DETAIL
# =========================================================

def movie_detail(request, movie_id):

    movie = get_object_or_404(
        Movie,
        id=movie_id
    )

    if movie.trailer_url:

        movie.trailer_original_url = (
            movie.trailer_url
        )

        parsed_url = urlparse(
            movie.trailer_url
        )

        video_id = parse_qs(
            parsed_url.query
        ).get(
            'v',
            [None]
        )[0]

        if video_id:

            movie.trailer_embed_url = (
                f'https://www.youtube.com/embed/'
                f'{video_id}'
            )

        else:
            movie.trailer_embed_url = (
                movie.trailer_url
            )

    posters = movie.posters.all()

    reviews = movie.reviews.all().order_by(
        '-created_at'
    )

    user_review = None

    if request.user.is_authenticated:
        user_review = reviews.filter(
            user=request.user
        ).first()

    for review in reviews:

        review.is_verified = Booking.objects.filter(
            user=review.user,
            movie=movie
        ).exists()

    similar_movies = Movie.objects.filter(
        genre=movie.genre
    ).exclude(
        id=movie.id
    )[:5]

    similar_by_language = Movie.objects.filter(
        language=movie.language
    ).exclude(
        id=movie.id
    )[:5]

    trending_movies = Movie.objects.order_by(
        '-popularity'
    )[:5]

    recently_released = Movie.objects.order_by(
        '-release_date'
    )[:5]

    recently_viewed = request.session.get(
        'recently_viewed',
        []
    )

    if movie_id not in recently_viewed:
        recently_viewed.append(movie_id)

    request.session['recently_viewed'] = recently_viewed[-5:]
    has_booked = False

    if request.user.is_authenticated:

        booking = Booking.objects.filter(
            user=request.user,
            movie=movie
        ).order_by(
            '-theater__time'
        ).first()

        if booking and booking.theater.time <= timezone.now():
            has_booked = True

    context = {
        'movie': movie,
        'posters': posters,
        'reviews': reviews,
        'user_review': user_review,
        'similar_movies': similar_movies,
        'similar_by_language': similar_by_language,
        'trending_movies': trending_movies,
        'recently_released': recently_released,
        'has_booked': has_booked,
    }

    return render(
        request,
        'movies/movie_detail.html',
        context
    )


# =========================================================
# ADD REVIEW
# =========================================================

@login_required
def add_review(request, movie_id):

    movie = get_object_or_404(
        Movie,
        id=movie_id
    )

    if request.method == 'POST':

        rating = request.POST.get('rating')
        comment = request.POST.get('comment')

        booking = Booking.objects.filter(
            user=request.user,
            movie=movie
        ).order_by(
            '-theater__time'
        ).first()

        if (
            not booking
            or booking.theater.time > timezone.now()
        ):

            return render(
                request,
                'movies/movie_detail.html',
                {
                    'movie': movie,
                    'error': (
                        'You can only review movies '
                        'after watching them.'
                    )
                }
            )

        review, created = Review.objects.update_or_create(
            movie=movie,
            user=request.user,
            defaults={
                'rating': rating,
                'comment': comment
            }
        )

        movie.update_rating()

        return redirect(
            'movie_detail',
            movie_id=movie.id
        )

    return redirect(
        'movie_detail',
        movie_id=movie.id
    )


# =========================================================
# EDIT REVIEW
# =========================================================

@login_required
def edit_review(request, review_id):

    review = get_object_or_404(
        Review,
        id=review_id,
        user=request.user
    )

    if request.method == 'POST':

        rating = request.POST.get('rating')
        comment = request.POST.get('comment')

        review.rating = rating
        review.comment = comment
        review.save()

        review.movie.update_rating()

        return redirect(
            'movie_detail',
            movie_id=review.movie.id
        )

    return redirect(
        'movie_detail',
        movie_id=review.movie.id
    )


# =========================================================
# REPORT REVIEW
# =========================================================

@login_required
def report_review(request, review_id):

    review = get_object_or_404(
        Review,
        id=review_id
    )

    if request.method == 'POST':

        review.is_reported = True
        review.save()

        return redirect(
            'movie_detail',
            movie_id=review.movie.id
        )

    return redirect(
        'movie_detail',
        movie_id=review.movie.id
    )


# =========================================================
# VERIFY PAYMENT
# =========================================================

@login_required
def verify_payment(request):

    if request.method != 'POST':
        return JsonResponse({
            'status': 'failed'
        })

    razorpay_payment_id = request.POST.get(
        'razorpay_payment_id'
    )

    razorpay_order_id = request.POST.get(
        'razorpay_order_id'
    )

    razorpay_signature = request.POST.get(
        'razorpay_signature'
    )

    try:

        # -------------------------------------------------
        # VERIFY RAZORPAY SIGNATURE
        # -------------------------------------------------

        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        })

        # -------------------------------------------------
        # FIND PENDING PAYMENTS
        # -------------------------------------------------

        payments = Payment.objects.filter(
            razorpay_order_id=razorpay_order_id,
            status='pending',
            booking__user=request.user
        )

        # -------------------------------------------------
        # DUPLICATE PROTECTION
        # -------------------------------------------------

        if not payments.exists():

            return JsonResponse({
                'status': 'success',
                'message': 'Payment already processed'
            })

        # -------------------------------------------------
        # CONFIRM BOOKINGS
        # -------------------------------------------------

        for payment in payments:

            booking = payment.booking

            existing_booking = Booking.objects.filter(
                seat=booking.seat,
                status='confirmed'
            ).exclude(
                id=booking.id
            ).first()

            if existing_booking:

                payment.status = 'failed'
                payment.razorpay_payment_id = (
                    razorpay_payment_id
                )
                payment.save()

                return JsonResponse({
                    'status': 'failed',
                    'message': (
                        'This seat has already been booked.'
                    )
                })

            payment.razorpay_payment_id = (
                razorpay_payment_id
            )

            payment.status = 'success'

            payment.save()

            if booking.status != 'confirmed':

                booking.status = 'confirmed'

                booking.seat.is_booked = True
                booking.seat.reserved_by = None
                booking.seat.reserved_at = None

                booking.seat.save()

                booking.save()

                generate_and_send_ticket.delay(
                    booking.id
                )

        return JsonResponse({
            'status': 'success'
        })

    except razorpay.errors.SignatureVerificationError:

        return JsonResponse({
            'status': 'failed',
            'message': 'Payment verification failed'
        })


# =========================================================
# PAYMENT FAILED
# =========================================================

@login_required
def payment_failed(request):
    razorpay_order_id = request.POST.get(
        'razorpay_order_id'
    )

    booking = Booking.objects.filter(
        user=request.user,
        status='pending',
        payments__razorpay_order_id=razorpay_order_id
    ).first()

    if not booking:

        return JsonResponse({
            'status': 'failed',
            'message': 'Payment already processed.'
        })

    bookings = Booking.objects.filter(
        user=request.user,
        status='pending',
        payments__razorpay_order_id=razorpay_order_id
    )

    for booking in bookings:

        booking.status = 'cancelled'
        booking.save()

        booking.seat.is_booked = False
        booking.seat.reserved_by = None
        booking.seat.reserved_at = None

        booking.seat.save()

        Payment.objects.filter(
            booking=booking,
            status='pending'
        ).update(
            status='failed'
        )

    return JsonResponse({
        'status': 'failed',
        'message': (
            'Payment failed and seats released.'
        )
    })


# =========================================================
# RAZORPAY WEBHOOK
# =========================================================

@csrf_exempt
def razorpay_webhook(request):

    if request.method != 'POST':

        return JsonResponse(
            {'status': 'failed'},
            status=400
        )

    webhook_signature = request.headers.get(
        'X-Razorpay-Signature'
    )

    try:

        razorpay_client.utility.verify_webhook_signature(
            request.body.decode('utf-8'),
            webhook_signature,
            settings.RAZORPAY_WEBHOOK_SECRET
        )

        data = json.loads(
            request.body
        )

        event = data.get('event')

        print(
            'RAZORPAY WEBHOOK:',
            event
        )

        # -------------------------------------------------
        # PAYMENT SUCCESS
        # -------------------------------------------------

        if event == 'payment.captured':

            payment_data = data[
                'payload'
            ][
                'payment'
            ][
                'entity'
            ]

            razorpay_payment_id = (
                payment_data['id']
            )

            razorpay_order_id = (
                payment_data['order_id']
            )

            payments = Payment.objects.filter(
                razorpay_order_id=razorpay_order_id,
                status='pending'
            )

            for payment in payments:

                booking = payment.booking

                if payment.status == 'success':
                    continue

                payment.razorpay_payment_id = (
                    razorpay_payment_id
                )

                payment.status = 'success'

                payment.save()

                if booking.status != 'confirmed':

                    booking.status = 'confirmed'

                    booking.seat.is_booked = True
                    booking.seat.reserved_by = None
                    booking.seat.reserved_at = None

                    booking.seat.save()

                    booking.save()

                    generate_and_send_ticket.delay(
                        booking.id
                    )

        # -------------------------------------------------
        # PAYMENT FAILED
        # -------------------------------------------------

        elif event == 'payment.failed':

            payment_data = data[
                'payload'
            ][
                'payment'
            ][
                'entity'
            ]

            razorpay_order_id = (
                payment_data['order_id']
            )

            payments = Payment.objects.filter(
                razorpay_order_id=razorpay_order_id,
                status='pending'
            )

            for payment in payments:

                booking = payment.booking

                payment.status = 'failed'
                payment.save()

                if booking.status == 'pending':

                    booking.status = 'cancelled'
                    booking.save()

                    booking.seat.is_booked = False
                    booking.seat.reserved_by = None
                    booking.seat.reserved_at = None

                    booking.seat.save()

        return JsonResponse({
            'status': 'success'
        })

    except Exception as e:

        print(
            'WEBHOOK ERROR:',
            e
        )

        return JsonResponse(
            {'status': 'failed'},
            status=400
        )


# =========================================================
# CHANGE SEATS
# =========================================================

@login_required(login_url='/login/')
def change_seats(request, booking_id):

    booking = get_object_or_404(
        Booking,
        id=booking_id,
        user=request.user,
        status='pending'
    )

    payment = Payment.objects.filter(
        booking=booking,
        status='pending'
    ).order_by(
        '-created_at'
    ).first()

    if payment:

        pending_bookings = Booking.objects.filter(
            user=request.user,
            status='pending',
            payments__razorpay_order_id=(
                payment.razorpay_order_id
            )
        ).distinct()

        with transaction.atomic():

            for pending_booking in pending_bookings:

                seat = Seat.objects.select_for_update().get(
                    id=pending_booking.seat_id
                )

                pending_booking.status = 'cancelled'
                pending_booking.save()

                Payment.objects.filter(
                    booking=pending_booking,
                    status='pending'
                ).update(
                    status='cancelled'
                )

                seat.is_booked = False
                seat.reserved_by = None
                seat.reserved_at = None

                seat.save()

    return redirect(
        'book_seats',
        theater_id=booking.theater_id
    )

# =========================================================
# CANCEL CONFIRMED BOOKING + RAZORPAY REFUND
# =========================================================

@login_required(login_url='/login/')
def cancel_booking(request, booking_id):

    if request.method != 'POST':
        return redirect('profile')

    booking = get_object_or_404(
        Booking,
        id=booking_id,
        user=request.user,
        status='confirmed'
    )

    payment = Payment.objects.filter(
        booking=booking
    ).order_by(
        '-created_at'
    ).first()

    if not payment:
        messages.error(
            request,
            'Payment record was not found.'
        )
        return redirect('profile')

    if payment.status == 'refunded':
        messages.info(
            request,
            'This booking has already been refunded.'
        )
        return redirect('profile')

    if payment.status != 'success':
        messages.error(
            request,
            'Only successfully paid bookings can be refunded.'
        )
        return redirect('profile')

    if not payment.razorpay_payment_id:
        messages.error(
            request,
            'Razorpay payment ID was not found. '
            'Refund cannot be processed.'
        )
        return redirect('profile')

    try:

        refund_amount = payment.amount

        refund_response = razorpay_client.payment.refund(
            payment.razorpay_payment_id,
            {
                'amount': int(
                    refund_amount * 100
                )
            }
        )

        if not refund_response or not refund_response.get('id'):
            messages.error(
                request,
                'Razorpay did not confirm the refund.'
            )
            return redirect('profile')

        with transaction.atomic():

            booking = Booking.objects.select_for_update().get(
                id=booking.id,
                user=request.user
            )

            payment = Payment.objects.select_for_update().get(
                id=payment.id
            )

            if payment.status == 'refunded':
                messages.info(
                    request,
                    'This payment has already been refunded.'
                )
                return redirect('profile')

            payment.status = 'refunded'
            payment.refund_amount = refund_amount

            payment.save(
                update_fields=[
                    'status',
                    'refund_amount'
                ]
            )

            booking.status = 'cancelled'

            booking.save(
                update_fields=['status']
            )

            seat = Seat.objects.select_for_update().get(
                id=booking.seat_id
            )

            seat.is_booked = False
            seat.reserved_by = None
            seat.reserved_at = None

            seat.save(
                update_fields=[
                    'is_booked',
                    'reserved_by',
                    'reserved_at'
                ]
            )

        messages.success(
            request,
            'Booking cancelled and refund processed successfully.'
        )

        return redirect('profile')

    except razorpay.errors.BadRequestError:

        messages.error(
            request,
            'Razorpay could not process the refund. '
            'Please try again.'
        )

        return redirect('profile')

    except Exception:

        messages.error(
            request,
            'Refund could not be processed. '
            'Please try again.'
        )

        return redirect('profile')
# =========================================================
# SEAT AVAILABILITY
# =========================================================

def seat_availability(request, theater_id):

    release_expired_reservations()

    theater = get_object_or_404(
        Theater,
        id=theater_id
    )

    seats = Seat.objects.filter(
        theater=theater
    )

    seat_data = []

    for seat in seats:

        if seat.is_booked:
            status = 'booked'

        elif seat.reserved_by:
            status = 'reserved'

        else:
            status = 'available'

        seat_data.append({
            'id': seat.id,
            'seat_number': seat.seat_number,
            'status': status,
        })

    return JsonResponse({
        'seats': seat_data
    })