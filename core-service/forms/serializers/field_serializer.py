from rest_framework import serializers
from forms.models import Field


class FieldOptionInputSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField(required=False)
    order = serializers.IntegerField()


class FieldSerializer(serializers.ModelSerializer):

    field_type_code = serializers.CharField(write_only=True)
    data_type_code = serializers.CharField(write_only=True)

    # 🔥 NEW
    options = FieldOptionInputSerializer(many=True, required=False)

    class Meta:
        model = Field
        fields = [
            'id',
            'name',
            'field_type_code',
            'data_type_code',
            'options'
        ]
        read_only_fields = ['id']

    def validate(self, data):

        field_type = data.get("field_type_code")
        options = data.get("options", [])

        # 🔥 RULE: selectable fields MUST have options
        if field_type in ["select", "radio", "checkbox"]:
            if not options:
                raise serializers.ValidationError(
                    "Selectable fields must include options"
                )

        return data