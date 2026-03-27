from django.db import models
from common.models import BaseModel

# represents a system module (Train, Arena, Events, etc.)
class Module(BaseModel):

    # human-readable name
    name = models.CharField(max_length=100)

    # unique identifier used in code
    code = models.CharField(max_length=100, unique=True)

    # indicates if the module is active in the system
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
