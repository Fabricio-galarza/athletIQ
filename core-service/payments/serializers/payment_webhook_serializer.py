from rest_framework import serializers

class PaymentWebhookSerializer(serializers.Serializer):

    # external payment id
    external_id = serializers.CharField()

    # payment status from provider
    status = serializers.ChoiceField(
        choices=["paid", "failed"]
    )