from rest_framework import serializers
from django.db.models import Q
from forms.models import FormField, Form


class OptionSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()
    order = serializers.IntegerField()


class FieldResponseSerializer(serializers.Serializer):

    #name = serializers.CharField()
    label = serializers.CharField()
    type = serializers.CharField(source='field.field_type.code')
    required = serializers.BooleanField(source='is_required')
    order = serializers.IntegerField()

    # 🔥 NEW
    options = serializers.SerializerMethodField()

    def get_options(self, obj):

        if obj.field.field_type.code not in ["select", "radio", "checkbox"]:
            return []

        return OptionSerializer(
            obj.field.options.all().order_by('order'),
            many=True
        ).data


class FormResponseSerializer(serializers.Serializer):

     fields = serializers.SerializerMethodField(method_name="get_fields_data")

     class Meta:
        model = Form
        fields = ["code", "name", "fields"]

     def get_fields_data(self, obj):

        sport_id = self.context.get("sport_id")

        fields_qs = obj.form_fields.filter(
            Q(sport_id=sport_id) | Q(sport__isnull=True)
        ).select_related(
            "field", "field__field_type"
        ).order_by("order")

        return FieldResponseSerializer(fields_qs, many=True).data