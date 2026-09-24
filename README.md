# BookMyShow Django Project

## Project Overview

This is a Django-based online movie booking application developed as part of the Elevance Skills internship program.

The project was developed by adding the required internship features to the existing Django training project.

## Tasks Completed

### Task 1 – Movie Search, Filtering and Recommendations

- Movie search
- Search and filtering by genre, language, city, theater, release date, rating and show time
- Sorting and pagination
- Trending and recently viewed movies
- Recommended movies

### Task 2 – Digital Ticket and Ticket History

- PDF ticket generation
- QR code generation
- Ticket download
- Ticket history
- Email delivery of tickets
- Retry support

### Task 3 – Movie and Review Management

- Movie management
- Theater and show schedule management
- Movie genres, languages and cast
- Multiple movie posters
- YouTube trailer
- Age certification and duration
- Reviews and ratings
- Automatic average rating
- Review editing and reporting
- Verified viewer badges
- Similar, trending and recently viewed movies

### Task 4 – Payment and Booking Management

- Razorpay test payment integration
- Pending and confirmed bookings
- Server-side payment verification
- Successful, failed and cancelled payment handling
- Seat release after failed or cancelled payments
- Payment transaction records
- Payment and booking history
- Retry payment
- Duplicate payment protection
- Razorpay webhook handling

### Task 5 – Smart Seat Reservation

- Live seat availability
- Multiple seat selection
- Temporary seat reservation
- Automatic reservation expiry
- Duplicate active booking protection
- Transaction-based booking logic

### Task 6 – Admin Dashboard

- Daily, weekly, monthly and yearly revenue
- Booking trends
- Theater occupancy percentage
- Most booked movies
- Top-performing theaters
- Peak booking hours
- Cancellation and refund statistics
- User growth
- Custom date filtering
- CSV export
- Optimized Django ORM queries
- Database indexes for performance

## Technology Stack

- Python
- Django
- HTML
- CSS
- JavaScript
- SQLite
- Razorpay Test API
- Celery
- Git
- GitHub

## Project Structure

```text
bookmyshow-django-project/
├── manage.py
├── name/
├── movies/
├── users/
├── templates/
├── media/
├── requirements.txt
├── vercel.json
├── release_expired_seats.bat
└── .gitignore

## Security

Sensitive configuration such as Django secret keys, Razorpay credentials and email credentials is stored using environment variables and is not included in the public repository.

## Testing

The implemented features were tested during development, including:

- Movie search and filtering
- Movie recommendations
- Ticket generation and email delivery
- Payment workflow
- Failed and cancelled payments
- Seat reservation and expiry
- Duplicate booking protection
- Admin dashboard analytics
- CSV export
- Performance testing with a large booking dataset

## Internship Details

**Program:** Elevance Skills Internship  
**Domain:** Web Development / Django  
**Project:** BookMyShow Django Project  
**Developer:** Prakruti Hiremath

## Future Improvements

- Production database and scalable background task infrastructure
- Additional payment providers
- More advanced recommendation features
- Enhanced analytics and visualizations
- Production monitoring and performance improvements