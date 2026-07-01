from rest_framework import serializers

# Serializer used to configue modules for a plan
class PlanModuleConfigSerializer(serializers.Serializer):
     
     # Module identifier (UUID)
     module_id  = serializers.UUIDField()

     # Indicators if module is enabled
     is_enabled = serializers.BooleanField()