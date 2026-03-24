from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
import uuid
from common.models import BaseModel

# Custom manager for user
# Here I control how users and superusers are created
class UserManager(BaseUserManager):
    # creating user
    def create_user(self, email, password=None, **extra_fields):
        # It is valid to include the email address because it 
        # will be the primary identifier.
        if not email:
            raise ValueError("El usuario debe tener un email")
        
        # I normalize the email (e.g., capital letters, etc.)
        email = self.normalize_email(email)

        # I create user instance
        user = self.model(email=email, **extra_fields)

        # I set password of secuity way(hash)
        user.set_password(password)

        # saving in database
        user.save(using=self._db)
        return user
    
    # creating superuser
    def create_superuser(self, email, password=None, **extra_fields):
        # For superuser access, I require these fields
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
       

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')

        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)
    
# user main user
# I ONLY handle authentication here; I don't enter personal data.
class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    # I use UUII because it is the best to microservices and
    # avoid exposing sequential IDs 
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # email like a unique identifier
    email       = models.EmailField(unique=True)

    # acces control flags
    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)

    # Personalized manager
    objects = UserManager()
     
    # I define that the login is done with email
    USERNAME_FIELD = 'email'

    # I don't need any additional required fields
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "usuario"

    def __str__(self):
        return super().__str__()
    



# stores personal information of the user
# separated from auth logic to keep the User model clean
class Profile(BaseModel):

    # one-to-one relationship with user
    # each user has exactly one profile
    user = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        related_name='profile'
    )

    # basic personal information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    # optional personal data
    birth_date = models.DateField(null=True, blank=True)

    # basic gender field (can evolve later)
    gender = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
# defines the type of profile a user can have
# example: athlete, coach, competitor
class ProfileType(BaseModel):

    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name
    

# relation between user and profile types
# allows a user to have multiple roles (athlete, coach, etc.)
class UserProfile(BaseModel):

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='user_profiles'
    )

    profile_type = models.ForeignKey(
        ProfileType,
        on_delete=models.CASCADE,
        related_name='user_profiles'
    )

    def __str__(self):
        return f"{self.user.email} - {self.profile_type.name}"