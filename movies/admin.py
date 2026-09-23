from django.contrib import admin
from .models import Movie, Theater, Seat, Booking, MoviePoster, Review, Genre, Language, Cast, Payment

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ['name', 'rating', 'cast', 'description', 'age_certification', 'duration', 'release_date', 'ticket_price', 'trailer_url']
    search_fields = ['name', 'genre', 'language']
    list_filter = ['age_certification', 'genre', 'language', 'release_date']

@admin.register(Theater)
class TheaterAdmin(admin.ModelAdmin):
    list_display = ['name', 'movie', 'time']

@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ['theater', 'seat_number', 'is_booked']

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['user', 'seat', 'movie','theater','booked_at']
    
@admin.register(MoviePoster)
class MoviePosterAdmin(admin.ModelAdmin):
    list_display = ['movie', 'image', 'order', 'uploaded_at']
    list_filter = ['movie']
    ordering = ['movie', 'order']

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['movie', 'user', 'rating', 'created_at', 'is_reported']
    list_filter = ['rating', 'is_reported', 'movie']
    search_fields = ['user__username', 'movie__name']
    
@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']
    
@admin.register(Cast)
class CastAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'created_at']
    search_fields = ['name']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['booking', 'transaction_id', 'status', 'amount', 'created_at']
    list_filter = ['status']
    search_fields = ['transaction_id']