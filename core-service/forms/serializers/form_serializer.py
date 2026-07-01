# forms/serializers/form_serializer.py
from rest_framework import serializers
from forms.models import Form

class FormSerializer(serializers.ModelSerializer):
    module_code = serializers.CharField(write_only=True)

    class Meta:
        model = Form
        fields = ['id', 'name', 'code', 'module_code', 'is_active']
        read_only_fields = ['id']

    def validate_code(self, value):
        if Form.objects.filter(code=value).exists():
            raise serializers.ValidationError("Form with this code already exists")
        return value
    
    def create(self, validated_data):
        validated_data.setdefault('is_active', False)
        return super().create(validated_data)


# Serializer específico para actualización parcial
class FormUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Form
        fields = ['is_active', 'name', 'code']
        # Todos los campos son opcionales para actualización parcial
        extra_kwargs = {
            'name': {'required': False},
            'code': {'required': False},
            'is_active': {'required': False}
        }
    
    def validate_code(self, value):
        # Excluir el formulario actual de la validación de unicidad
        if self.instance and self.instance.code != value:
            if Form.objects.filter(code=value).exists():
                raise serializers.ValidationError("Form with this code already exists")
        return value