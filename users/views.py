from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from .forms import UserRegisterForm, UserUpdateForm
from django.shortcuts import render,redirect
from django.db.models import Q
from django.contrib.auth import login,authenticate
from django.contrib.auth.decorators import login_required
from movies.models import Movie, Booking, Payment

def home(request):
    movies = Movie.objects.all()

    recommended_movies = Movie.objects.none()

    if request.user.is_authenticated:
        booked_genres = Booking.objects.filter(
            user=request.user
        ).values_list('movie__genre', flat=True).distinct()

        viewed_movies = request.session.get('recently_viewed', [])

        recommended_movies = Movie.objects.filter(
            Q(genre__in=booked_genres) |
            Q(id__in=viewed_movies)
        ).exclude(
            id__in=Booking.objects.filter(
                user=request.user
            ).values_list('movie_id', flat=True)
        ).distinct()

    return render(
        request,
        'home.html',
        {
            'movies': movies,
            'recommended_movies': recommended_movies
        }
    )
def register(request):
    if request.method == 'POST':
        form=UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username=form.cleaned_data.get('username')
            password=form.cleaned_data.get('password1')
            user=authenticate(username=username,password=password)
            login(request,user)
            return redirect('profile')
    else:
        form=UserRegisterForm()
    return render(request,'users/register.html',{'form':form})
def login_view(request):
    
    if request.method == 'POST':

        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():

            user = form.get_user()

            login(request, user)

            next_url = request.GET.get('next') or request.POST.get('next')
            return redirect(next_url or '/')

    else:
        form = AuthenticationForm()

    return render(request, 'users/login.html', {'form': form})

@login_required
def profile(request):
    bookings= Booking.objects.filter(user=request.user)
    payments = Payment.objects.filter(
    booking__user=request.user
    ).order_by('-created_at')
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        if u_form.is_valid():
            u_form.save()
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)

    return render(request, 'users/profile.html', {'u_form': u_form,'bookings':bookings ,'payments':payments})

@login_required
def reset_password(request):
    if request.method == 'POST':
        form=PasswordChangeForm(user=request.user,data=request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form=PasswordChangeForm(user=request.user)
    return render(request,'users/reset_password.html',{'form':form})