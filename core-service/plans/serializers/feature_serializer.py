from rest_framework import serializers
from plans.models import Feature

# serializer for Feature model
class FeatureSerializer(serializers.ModelSerializer):

    # automatically resolves module from UUID
    module_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Feature
        fields = [
            "id",
            "name",
            "code",
            "module_id",
            "created_at",
            "updated_at",
        ]

    # validate unique code
    def validate_code(self, value):

        queryset = Feature.objects.filter(code__iexact=value)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError("Feature code already exists")

        return value