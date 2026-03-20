from django.db import models
from common.models import BaseModel


# defines roles in the system
# examples: admin, coach, athlete
class Role(BaseModel):

    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
# defines a specific action that can be performed in the system
# examples:
# - create_training_plan
# - edit_training_plan
# - delete_training_plan
class Permission(BaseModel):

    # human-readable name
    name = models.CharField(max_length=100)

    # unique identifier used in code
    code = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
# defines which permissions are assigned to each role
# this allows flexible permission management per role
class RolePermission(BaseModel):

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='role_permissions'
    )

    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='role_permissions'
    )

    def __str__(self):
        return f"{self.role.name} - {self.permission.code}"
    
# assigns roles to users
# a user can have multiple roles (e.g. coach + athlete)
class UserRole(BaseModel):

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='user_roles'
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_roles'
    )

    def __str__(self):
        return f"{self.user.email} - {self.role.name}"