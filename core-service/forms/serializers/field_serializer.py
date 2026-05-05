# forms/serializers/field_serializer.py
from rest_framework import serializers
from forms.models import Field


class FieldOptionInputSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField(required=False)
    order = serializers.IntegerField(required=False, default=0)


class FieldSerializer(serializers.ModelSerializer):

    field_type_code = serializers.CharField(write_only=True)
    data_type_code = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)
    ui_config = serializers.JSONField(required=False, default=dict)
    options = FieldOptionInputSerializer(many=True, required=False)

    class Meta:
        model = Field
        fields = [
            'id',
            'name',
            'field_type_code',
            'data_type_code',
            'ui_config',
            'options'
        ]
        read_only_fields = ['id']

    def validate(self, data):
        field_type_code = data.get("field_type_code")
        data_type_code = data.get("data_type_code")
        options = data.get("options", [])
        
        ui_only_types = [
                            "section",
                            "subheader",
                            "dynamic_selects", 
                            "html",
                            "divider",
                            "spacer",
                            "info_box"
                        ]
        
        if field_type_code in ui_only_types:
            if data_type_code:
                raise serializers.ValidationError(
                    f"Field type '{field_type_code}' is UI-only and should not have data_type"
                )
        else:
            if not data_type_code:
                raise serializers.ValidationError(
                    f"Field type '{field_type_code}' requires a data_type"
                )

        if field_type_code in ["select", "radio", "checkbox"]:
            if not options:
                raise serializers.ValidationError(
                    "Selectable fields must include options"
                )

        return data

    def to_representation(self, instance):
        """🔥 Controlar la salida para UI-only fields"""
        representation = super().to_representation(instance)
        
        # Para UI-only fields, data_type_code puede ser None
        if instance.data_type is None:
            representation['data_type_code'] = None
        
        return representation