from django.urls import path

from sports.views.sport_view import sportListview
from sports.views.user_sports_view import UserSportView

urlpatterns = [
    path('sports/', sportListview.as_view(), name='get-sports'),
    path('users/me/sports/', UserSportView.as_view(), name='update-user-sports')
]