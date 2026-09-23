import csv
from datetime import datetime

from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
from django.http import HttpResponse
from django.db.models import (
    Sum,
    Count,
    Q,
    ExpressionWrapper,
    FloatField,
    Case,
    When,
    F
)
from django.utils import timezone
from django.db.models.functions import TruncDate, ExtractHour
from django.contrib.auth.models import User

from .models import Payment, Booking, Seat


def admin_required(view_func):
    return user_passes_test(
        lambda user: user.is_authenticated and user.is_staff,
        login_url='/users/login/'
    )(view_func)

@admin_required
def admin_dashboard(request):
    today = timezone.localdate()

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    date_filter = {}

    if start_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

    if end_date:
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    # ---------------- REVENUE ----------------

    if start_date and end_date:
        start_datetime = timezone.make_aware(
            datetime.combine(start_date, datetime.min.time())
        )

        end_datetime = timezone.make_aware(
            datetime.combine(
                end_date + timezone.timedelta(days=1),
                datetime.min.time()
            )
        )

        daily_revenue = Payment.objects.filter(
            status='success',
            created_at__gte=start_datetime,
            created_at__lt=end_datetime
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

        weekly_revenue = Payment.objects.filter(
            status='success',
            created_at__gte=start_datetime,
            created_at__lt=end_datetime
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

        monthly_revenue = Payment.objects.filter(
            status='success',
            created_at__gte=start_datetime,
            created_at__lt=end_datetime
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

        yearly_revenue = Payment.objects.filter(
            status='success',
            created_at__gte=start_datetime,
            created_at__lt=end_datetime
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

    else:
        daily_revenue = Payment.objects.filter(
            status='success',
            created_at__date=today
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

        weekly_revenue = Payment.objects.filter(
            status='success',
            created_at__date__gte=today - timezone.timedelta(days=6),
            created_at__date__lte=today
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

        monthly_revenue = Payment.objects.filter(
            status='success',
            created_at__year=today.year,
            created_at__month=today.month
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

        yearly_revenue = Payment.objects.filter(
            status='success',
            created_at__year=today.year
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

    # ---------------- BOOKING TRENDS ----------------

    booking_trends = (
        Booking.objects
        .filter(
            status='confirmed',
            booked_at__date__gte=start_date if start_date else today - timezone.timedelta(days=6),
            booked_at__date__lte=end_date if end_date else today
        )
        .values('booked_at__date')
        .annotate(total=Count('id'))
        .order_by('booked_at__date')
    )

    # ---------------- THEATER OCCUPANCY ----------------

    theater_occupancy = (
        Seat.objects
        .values('theater__name')
        .annotate(
            total_seats=Count('id'),
            booked_seats=Count(
                'id',
                filter=Q(is_booked=True)
            )
        )
        .annotate(
            occupancy_percentage=Case(
                When(
                    total_seats=0,
                    then=0
                ),
                default=ExpressionWrapper(
                    F('booked_seats') * 100.0 / F('total_seats'),
                    output_field=FloatField()
                ),
                output_field=FloatField()
            )
        )
        .order_by('theater__name')
    )

    # ---------------- MOST BOOKED MOVIES ----------------

    most_booked_movies = (
        Booking.objects
        .filter(
            status='confirmed',
            booked_at__date__gte=start_date if start_date else today - timezone.timedelta(days=6),
            booked_at__date__lte=end_date if end_date else today
        )
        .values('movie__name')
        .annotate(total_bookings=Count('id'))
        .order_by('-total_bookings')
    )

    # ---------------- TOP THEATERS ----------------

    top_theaters = (
        Booking.objects
        .filter(
            status='confirmed',
            booked_at__date__gte=start_date if start_date else today - timezone.timedelta(days=6),
            booked_at__date__lte=end_date if end_date else today
        )
        .values('theater__name')
        .annotate(total_bookings=Count('id'))
        .order_by('-total_bookings')
    )

    # ---------------- PEAK BOOKING HOURS ----------------

    peak_booking_hours = (
        Booking.objects
        .filter(
            status='confirmed',
            booked_at__date__gte=start_date if start_date else today - timezone.timedelta(days=6),
            booked_at__date__lte=end_date if end_date else today
        )
        .values('booked_at__hour')
        .annotate(total_bookings=Count('id'))
        .order_by('-total_bookings')
    )

    # ---------------- CANCELLATIONS ----------------

    cancelled_bookings = Booking.objects.filter(
        status='cancelled',
        booked_at__date__gte=start_date if start_date else today - timezone.timedelta(days=6),
        booked_at__date__lte=end_date if end_date else today
    ).count()

    cancelled_payments = Payment.objects.filter(
        status='cancelled',
        created_at__date__gte=start_date if start_date else today - timezone.timedelta(days=6),
        created_at__date__lte=end_date if end_date else today
    ).count()

    failed_payments = Payment.objects.filter(
        status='failed',
        created_at__date__gte=start_date if start_date else today - timezone.timedelta(days=6),
        created_at__date__lte=end_date if end_date else today
    ).count()

    # ---------------- REFUNDS ----------------

    refunded_payments = Payment.objects.filter(
        status='refunded',
        created_at__date__gte=start_date if start_date else today - timezone.timedelta(days=6),
        created_at__date__lte=end_date if end_date else today
    ).count()

    refund_amount = Payment.objects.filter(
        status='refunded',
        created_at__date__gte=start_date if start_date else today - timezone.timedelta(days=6),
        created_at__date__lte=end_date if end_date else today
    ).aggregate(
        total=Sum('refund_amount')
    )['total'] or 0

    # ---------------- USER GROWTH ----------------

    user_growth = (
        User.objects
        .filter(
            date_joined__date__gte=start_date if start_date else today - timezone.timedelta(days=6),
            date_joined__date__lte=end_date if end_date else today
        )
        .values('date_joined__date')
        .annotate(total_users=Count('id'))
        .order_by('date_joined__date')
    )

    context = {
        'daily_revenue': daily_revenue,
        'weekly_revenue': weekly_revenue,
        'monthly_revenue': monthly_revenue,
        'yearly_revenue': yearly_revenue,
        'booking_trends': booking_trends,
        'theater_occupancy': theater_occupancy,
        'most_booked_movies': most_booked_movies,
        'top_theaters': top_theaters,
        'peak_booking_hours': peak_booking_hours,
        'cancelled_bookings': cancelled_bookings,
        'cancelled_payments': cancelled_payments,
        'failed_payments': failed_payments,
        'refunded_payments': refunded_payments,
        'refund_amount': refund_amount,
        'user_growth': user_growth,
        'start_date': start_date,
        'end_date': end_date
    }

    return render(
        request,
        'movies/admin_dashboard.html',
        context
    )
@admin_required
def export_dashboard_csv(request):

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    today = timezone.localdate()

    # ---------------- DATE RANGE ----------------

    if start_date and end_date:
        start_date = datetime.strptime(
            start_date,
            "%Y-%m-%d"
        ).date()

        end_date = datetime.strptime(
            end_date,
            "%Y-%m-%d"
        ).date()

    else:
        start_date = today - timezone.timedelta(days=6)
        end_date = today

    start_datetime = timezone.make_aware(
        datetime.combine(
            start_date,
            datetime.min.time()
        )
    )

    end_datetime = timezone.make_aware(
        datetime.combine(
            end_date + timezone.timedelta(days=1),
            datetime.min.time()
        )
    )

    # ---------------- REVENUE ----------------

    revenue_queryset = Payment.objects.filter(
        status='success',
        created_at__gte=start_datetime,
        created_at__lt=end_datetime
    )

    total_revenue = revenue_queryset.aggregate(
        total=Sum('amount')
    )['total'] or 0

    # For a custom range, all revenue values represent
    # the selected date range.
    daily_revenue = total_revenue
    weekly_revenue = total_revenue
    monthly_revenue = total_revenue
    yearly_revenue = total_revenue

    # ---------------- BOOKING BASE QUERY ----------------

    confirmed_bookings = Booking.objects.filter(
        status='confirmed',
        booked_at__gte=start_datetime,
        booked_at__lt=end_datetime
    )

    # ---------------- BOOKING STATISTICS ----------------

    total_bookings = confirmed_bookings.count()

    cancelled_bookings = Booking.objects.filter(
        status='cancelled',
        booked_at__gte=start_datetime,
        booked_at__lt=end_datetime
    ).count()

    cancelled_payments = Payment.objects.filter(
        status='cancelled',
        created_at__gte=start_datetime,
        created_at__lt=end_datetime
    ).count()

    failed_payments = Payment.objects.filter(
        status='failed',
        created_at__gte=start_datetime,
        created_at__lt=end_datetime
    ).count()

    refunded_payments = Payment.objects.filter(
        status='refunded',
        created_at__gte=start_datetime,
        created_at__lt=end_datetime
    ).count()

    refund_amount = Payment.objects.filter(
        status='refunded',
        created_at__gte=start_datetime,
        created_at__lt=end_datetime
    ).aggregate(
        total=Sum('refund_amount')
    )['total'] or 0

    # ---------------- CSV RESPONSE ----------------

    response = HttpResponse(
        content_type='text/csv'
    )

    response['Content-Disposition'] = (
        'attachment; filename="admin_dashboard_report.csv"'
    )

    writer = csv.writer(response)

    writer.writerow(['Admin Dashboard Report'])
    writer.writerow([
        'Date Range',
        f'{start_date} to {end_date}'
    ])
    writer.writerow([])

    # ---------------- REVENUE ----------------

    writer.writerow(['Revenue'])
    writer.writerow(['Daily Revenue', daily_revenue])
    writer.writerow(['Weekly Revenue', weekly_revenue])
    writer.writerow(['Monthly Revenue', monthly_revenue])
    writer.writerow(['Yearly Revenue', yearly_revenue])
    writer.writerow([])

    # ---------------- BOOKING STATISTICS ----------------

    writer.writerow(['Booking Statistics'])
    writer.writerow(['Total Bookings', total_bookings])
    writer.writerow(['Cancelled Bookings', cancelled_bookings])
    writer.writerow(['Cancelled Payments', cancelled_payments])
    writer.writerow(['Failed Payments', failed_payments])
    writer.writerow(['Refunded Payments', refunded_payments])
    writer.writerow(['Total Refund Amount', refund_amount])
    writer.writerow([])

    # ---------------- BOOKING TRENDS ----------------

    writer.writerow(['Booking Trends'])

    booking_trends = (
        confirmed_bookings
        .values('booked_at__date')
        .annotate(
            total=Count('id')
        )
        .order_by('booked_at__date')
    )

    for item in booking_trends:
        writer.writerow([
            item['booked_at__date'],
            item['total']
        ])

    # ---------------- THEATER OCCUPANCY ----------------

    writer.writerow([])
    writer.writerow(['Theater Occupancy'])

    theater_occupancy = (
        Seat.objects
        .values('theater__name')
        .annotate(
            total_seats=Count('id'),
            booked_seats=Count(
                'id',
                filter=Q(is_booked=True)
            )
        )
        .annotate(
            occupancy_percentage=Case(
                When(
                    total_seats=0,
                    then=0
                ),
                default=ExpressionWrapper(
                    F('booked_seats') * 100.0 / F('total_seats'),
                    output_field=FloatField()
                ),
                output_field=FloatField()
            )
        )
        .order_by('theater__name')
    )

    for theater in theater_occupancy:
        writer.writerow([
            theater['theater__name'],
            theater['booked_seats'],
            theater['total_seats'],
            theater['occupancy_percentage']
        ])

    # ---------------- MOST BOOKED MOVIES ----------------

    writer.writerow([])
    writer.writerow(['Most Booked Movies'])

    most_booked_movies = (
        confirmed_bookings
        .values('movie__name')
        .annotate(
            total_bookings=Count('id')
        )
        .order_by('-total_bookings')
    )

    for movie in most_booked_movies:
        writer.writerow([
            movie['movie__name'],
            movie['total_bookings']
        ])

    # ---------------- TOP THEATERS ----------------

    writer.writerow([])
    writer.writerow(['Top-Performing Theaters'])

    top_theaters = (
        confirmed_bookings
        .values('theater__name')
        .annotate(
            total_bookings=Count('id')
        )
        .order_by('-total_bookings')
    )

    for theater in top_theaters:
        writer.writerow([
            theater['theater__name'],
            theater['total_bookings']
        ])

    # ---------------- PEAK BOOKING HOURS ----------------

    writer.writerow([])
    writer.writerow(['Peak Booking Hours'])

    peak_booking_hours = (
        confirmed_bookings
        .values('booked_at__hour')
        .annotate(
            total_bookings=Count('id')
        )
        .order_by('-total_bookings')
    )

    for hour in peak_booking_hours:
        writer.writerow([
            hour['booked_at__hour'],
            hour['total_bookings']
        ])

    # ---------------- USER GROWTH ----------------

    writer.writerow([])
    writer.writerow(['User Growth'])

    user_growth = (
        User.objects
        .filter(
            date_joined__gte=start_datetime,
            date_joined__lt=end_datetime
        )
        .values('date_joined__date')
        .annotate(
            total_users=Count('id')
        )
        .order_by('date_joined__date')
    )

    for user in user_growth:
        writer.writerow([
            user['date_joined__date'],
            user['total_users']
        ])

    return response