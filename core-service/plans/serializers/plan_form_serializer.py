from rest_framework import serializers

# Seralizer to configurations form from plan
class PlanFormConfigSerializer(serializers.Serializer):

    form_id = serializers.UUIDField()
    code    = serializers.CharField()
    is_enabled = serializers.BooleanField()