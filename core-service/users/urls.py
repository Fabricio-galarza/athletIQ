from django.urls import path
from users.views.register_view import RegisterView
from users.views.user_access_view import UserAccessView
from users.views.login_view import LoginView

urlpatterns = [
    path("auth/register/", RegisterView.as_view()),
    path("auth/login/", LoginView.as_view()),
    path("users/me/access/", UserAccessView.as_view()),
]