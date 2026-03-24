from django.urls import path
from users.views.register_view import RegisterView
from users.views.login_view import LoginView

urlpatterns = [
    path("auth/register/", RegisterView.as_view()),
    path("auth/login/", LoginView.as_view()),
]