from django.db import models
from common.models import BaseModel


# defines a sport in the system
# examples: running, crossfit, swimming
class Sport(BaseModel):

    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
# relation between users and sports
# a user can practice multiple sports
class UserSport(BaseModel):

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='user_sports'
    )

    sport = models.ForeignKey(
        Sport,
        on_delete=models.CASCADE,
        related_name='user_sports'
    )

    def __str__(self):
        return f"{self.user.email} - {self.sport.name}"