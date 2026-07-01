from rest_framework import serializers


# serializer used to configure features for a plan
class PlanFeatureConfigSerializer(serializers.Serializer):

    # feature identifier
    feature_id = serializers.UUIDField()

    # feature code
    Code       = serializers.CharField()
    # indicates if the feature is enabled or disabled
    is_enabled = serializers.BooleanField()