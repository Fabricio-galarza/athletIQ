from rest_framework import serializers
from django.contrib.auth.password_validation  import validate_password
from common.validators import OnlyLettersValidator


from users.models import User, Profile

class ProfileSeralizer(serializers.ModelSerializer):

    # Customizing feilds validations profile
    first_name = serializers.CharField(validators=[OnlyLettersValidator()])
    last_name = serializers.CharField(validators=[OnlyLettersValidator()])
    
    class Meta:
        model = Profile
        fields = ['last_name', 'first_name']

        

# serializer used only to validate request data
class RegisterSerializer(serializers.ModelSerializer):
    profile = ProfileSeralizer()

    # customizing email required message
   
    class Meta:
        model = User
        fields = ['email', 'password', 'profile']
        extra_kwargs = {
            "email": {
                "validators": []  # ✅ aquí sí
            }
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("El email ya esta registrado")
        return value

    def validate_password(self, value):
        validate_password(value)

        if value.lower() == "password":
            raise serializers.ValidationError("Contraseña demasiado débil.")

        return value
        
