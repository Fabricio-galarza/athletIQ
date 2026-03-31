from rest_framework import serializers
from plans.models import Plan

# Serializer fro Plan Model
# user for create, update and read operations
class PlanSerializer(serializers.ModelSerializer):

    class Meta:
        model  = Plan
        fields = [
            "id",
            "name",
            "description",
            "price",
            "is_active",
            "created_at",
            "updated_at"
        ]
        extra_kwargs = {
            "name": {
                "validators": []
            }
        }

    # validate that the plan name is unique (extra safety)
    def validate_name(self, value):
        print("VALUE:", value)
        print("INSTANCE ID:", self.instance.id if self.instance else None)
        queryset = Plan.objects.filter(name=value)
        print("QUERYSET BEFORE EXCLUDE:", queryset)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
            
        print("QUERYSET AFTER EXCLUDE:", queryset)
        if queryset.exists():
            print("DUPLICATE FOUND")
            raise serializers.ValidationError("Plan already exists")

        return value