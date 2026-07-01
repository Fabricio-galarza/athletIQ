from rest_framework import serializers
from payments.models import Payment

class PaymentSerializer(serializers.ModelSerializer):

    # get pla_id
    plan_id = serializers.UUIDField(write_only=True)

    class Meta:
        model  = Payment
        fields = [
            "id",
            "plan_id",
            "amount",
            "status",
            "created_at"
        ]
        read_only_fields = ["id", "amount", "status", "created_by"]

        