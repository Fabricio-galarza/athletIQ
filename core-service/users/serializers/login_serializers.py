from rest_framework import serializers


class LoginSerizalizer(serializers.Serializer):
  
    # Customizing feilds validations profile
    email = serializers.EmailField()
    password = serializers.CharField(write_only = True) # Only for write, not for read