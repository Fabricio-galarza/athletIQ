import re
from rest_framework import serializers

class OnlyLettersValidator:
    def __call__(self, value):
        if not value:
            raise serializers.ValidationError("FIELD_REQUIRED")

        if not re.match(r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$', value):
            raise serializers.ValidationError("SOLO PERMITRE LETRAS")