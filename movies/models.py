from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User 


class Movie(models.Model):
    name= models.CharField(max_length=255)
    image= models.ImageField(upload_to="movies/")
    rating = models.DecimalField(max_digits=3,decimal_places=1)
    cast= models.TextField()
    description= models.TextField(blank=True,null=True) # optional
    
    genre = models.CharField(max_length=50, blank=True)
    language = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=50, blank=True)
    release_date = models.DateField(null=True, blank=True)
    ticket_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    popularity = models.IntegerField(default=0)
        # Task 3 - New fields
    trailer_url = models.URLField(max_length=500, blank=True, null=True)
    age_certification = models.CharField(max_length=20, blank=True, null=True)
    duration = models.PositiveIntegerField(blank=True, null=True, help_text="Duration in minutes")

    
    def __str__(self):
        return self.name
    def update_rating(self):
        reviews = self.reviews.all()
        if reviews.exists():
            avg = sum(r.rating for r in reviews) / reviews.count()
            self.rating = round(avg, 1)
        else:
            self.rating = 0
        self.save()


class Theater(models.Model):
    name = models.CharField(max_length=255)
    movie = models.ForeignKey(Movie,on_delete=models.CASCADE,related_name='theaters')
    time= models.DateTimeField()
    screen = models.CharField(max_length=100, default="Screen 1")

    def __str__(self):
        return f'{self.name} - {self.movie.name} at {self.time}'

class Seat(models.Model):
    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE,
        related_name='seats'
    )
    seat_number = models.CharField(max_length=10)
    is_booked = models.BooleanField(default=False)

    reserved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    reserved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.seat_number} in {self.theater.name}'
    
class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    seat = models.ForeignKey(
        Seat,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE
    )

    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE
    )

    booked_at = models.DateTimeField(
        auto_now_add=True
    )

    payment_reference = models.CharField(
        max_length=100,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    def __str__(self):
        return f'Booking by {self.user.username} for {self.seat.seat_number} at {self.theater.name}'

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['seat'],
                condition=Q(
                    status__in=['pending', 'confirmed']
                ),
                name='unique_active_booking_per_seat'
            )
        ]

        indexes = [
            models.Index(
                fields=['booked_at']
            ),

            models.Index(
                fields=['status', 'booked_at']
            ),

            models.Index(
                fields=['movie', 'status', 'booked_at']
            ),

            models.Index(
                fields=['theater', 'status', 'booked_at']
            ),
        ]
        
class MoviePoster(models.Model):
        movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='posters')
        image = models.ImageField(upload_to='movie_posters/')
        caption = models.CharField(max_length=100, blank=True, null=True)
        order = models.PositiveIntegerField(default=0)
        uploaded_at = models.DateTimeField(auto_now_add=True)

        class Meta: 
            ordering = ['order', 'uploaded_at']

        def __str__(self):
            return f"Poster for {self.movie.name} ({self.order})"
        
class Review(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(help_text="Rating from 1 to 5")
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_reported = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['movie', 'user']  # One review per user per movie
        
    def __str__(self):
        return f"{self.user.username} - {self.movie.name} ({self.rating}/5)"
    
class Genre(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class Language(models.Model):
    name = models.CharField(max_length=30, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class Cast(models.Model):
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Payment(models.Model):
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    transaction_id = models.CharField(max_length=200, unique=True)
    razorpay_order_id = models.CharField(max_length=200, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.booking.id} - {self.status}"