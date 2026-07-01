from django.contrib import admin
from django.urls import path, include
from core.views.access_view import AccessMeView

urlpatterns = [
    path('admin/', admin.site.urls),
     path('access/me/', AccessMeView.as_view()),

    # user urls
    path("api/v1/", include("users.urls")),
    path("api/v1/", include("users.urls")),

    # plan urls
    path("api/v1/", include("plans.urls")),

    # forms url
    path('api/v1/', include('forms.urls')),

    # payment url
    path('api/v1/', include('payments.urls')),

    #sports urls
    path('api/v1/', include('sports.urls')),

    path('api/v1/users/me/context/', AccessMeView.as_view(), name='user-context'),
]
