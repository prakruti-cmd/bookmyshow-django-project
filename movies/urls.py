from django.urls import path
from . import views
from .admin_dashboard import admin_dashboard, export_dashboard_csv
urlpatterns=[
    path('',views.movie_list,name='movie_list'),
    path('<int:movie_id>/theaters',views.theater_list,name='theater_list'),
    path('theater/<int:theater_id>/seats/book/',views.book_seats,name='book_seats'),
    path('theater/<int:theater_id>/seats/availability/', views.seat_availability, name='seat_availability'),
    path('payment/<int:booking_id>/', views.payment_page, name='payment_page'),
    path('payment/change-seats/<int:booking_id>/', views.change_seats, name='change_seats'),
    path('payment/retry/<int:booking_id>/', views.retry_payment, name='retry_payment'),
    path('payment/cancel/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('payment/verify/', views.verify_payment, name='verify_payment'),
    path('payment/webhook/', views.razorpay_webhook, name='razorpay_webhook'),
    path('payment/failed/', views.payment_failed, name='payment_failed'),
    path('ticket/<int:booking_id>/download/',views.download_ticket,name='download_ticket'),
    path('movie/<int:movie_id>/', views.movie_detail, name='movie_detail'),
    path('movie/<int:movie_id>/review/', views.add_review, name='add_review'),
    path('review/<int:review_id>/edit/', views.edit_review, name='edit_review'),
    path('review/<int:review_id>/report/', views.report_review, name='report_review'),
    path('admin/dashboard/', admin_dashboard, name='admin_dashboard'),
    path('admin/dashboard/export/', export_dashboard_csv, name='export_dashboard_csv'),
]