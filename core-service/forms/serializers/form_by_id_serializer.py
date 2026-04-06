from rest_framework import serializers


class OptionSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()
    order = serializers.IntegerField()


class FieldResponseSerializer(serializers.Serializer):

    name = serializers.CharField(source='field.name')
    label = serializers.CharField()
    type = serializers.CharField(source='field.field_type.code')
    required = serializers.BooleanField(source='is_required')
    order = serializers.IntegerField()

    # include options if applicable
    options = serializers.SerializerMethodField()

    def get_options(self, obj):

        if obj.field.field_type.code not in ["select", "radio", "checkbox"]:
            return []

        return OptionSerializer(
            obj.field.options.all().order_by('order'),
            many=True
        ).data


class FormResponseSerializer(serializers.Serializer):

    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    fields = FieldResponseSerializer(many=True)