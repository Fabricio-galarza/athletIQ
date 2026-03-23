from django.urls import path
from users.views.register_view import RegisterView

urlpatterns = [
    path("auth/register/", RegisterView.as_view()),
]