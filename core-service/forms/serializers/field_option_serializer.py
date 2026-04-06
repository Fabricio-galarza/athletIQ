from rest_framework import serializers
from forms.models import FieldOPtion


class FieldOptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = FieldOPtion
        fields = [
            'id',
            'value',
            'label',
            'order'
        ]
        read_only_fields = ['id']