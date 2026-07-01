from django.utils import timezone

from plans.models import Feature
from modules.models import Module


# creates a new feature
def create_feature(validated_data, user = None):

    module_id = validated_data.pop("module_id")
   
    try:
        module = Module.objects.get(id=module_id)
    except Module.DoesNotExist:
        raise Exception("Module not found")

    validated_data["module"] = module


    validated_data["code"] = validated_data["code"].strip().lower()

    return Feature.objects.create(
        **validated_data, 
        created_by = user,
        created_at = timezone.now())


# updates a feature
def update_feature(feature, validated_data):

    for attr, value in validated_data.items():
        setattr(feature, attr, value)

    feature.save()

    return feature