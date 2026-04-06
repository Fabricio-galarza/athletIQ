from rest_framework import serializers
from forms.models import FormField, Field


class FormFieldSerializer(serializers.ModelSerializer):

    # receive field as UUID
    field_id = serializers.UUIDField(write_only=True)

    # sport (UUID)
    sport_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = FormField
        fields = [
            'id',
            'field_id',
            'sport_id',
            'label',
            'is_required',
            'order'
        ]
        read_only_fields = ['id']

    def validate(self, data):
        """
        validate business rules at serializer level (light validation)
        """

        # validate order
        if data.get("order", 0) < 0:
            raise serializers.ValidationError("Order must be >= 0")

        return data