from django.contrib import admin
from users.models import User, Profile, ProfileType, UserProfile 

admin.site.register(User)
admin.site.register(Profile)
admin.site.register(ProfileType)
admin.site.register(UserProfile)
