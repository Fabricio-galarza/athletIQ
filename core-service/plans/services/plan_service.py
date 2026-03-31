from plans.models import Plan, PlanFeature, Feature, PlanModule
from modules.models import Module
from rest_framework.exceptions import ValidationError

# create a new subscription plan
def create_plan(validated_data):

    # create and return the plan
    plan = Plan.objects.create(**validated_data)

    return plan

# updates an existing plan
def update_plan(plan, validated_data):
    
    # update fields dynamically
    for attr, value in validated_data.items():
        setattr(plan, attr, value)

    plan.save()

    return plan

# Sets fetures configuration for a given plan
def set_plan_features(plan, features_data):

    # iterate oever incoming feature configurations
    for item in features_data:

        feature_id = item.get("feature_id")
        is_enabled = item.get("is_enabled")

        try:
            feature = Feature.objects.get(id=feature_id)
        except Feature.DoesNotExist:
            raise ValidationError(f"Feature {feature_id} does not exist")

        # 🔥 VALIDATION: module must be enabled in plan
        if not PlanModule.objects.filter(
            plan=plan,
            module=feature.module,
            is_enabled=True
        ).exists():
            raise ValidationError(
                f"Module {feature.module.code} is not enabled for this plan"
            )

        PlanFeature.objects.update_or_create(
            plan=plan,
            feature=feature,
            defaults={"is_enabled": is_enabled}
        )

    return True

# sets modules configuration for a given plan
def set_plan_modules(plan, modules_data):

    enabled_modules_count = 0

    for item in modules_data:

        module_id = item.get("module_id")
        is_enabled = item.get("is_enabled")

        try:
            module = Module.objects.get(id=module_id)
        except Module.DoesNotExist:
            raise ValidationError(f"Module {module_id} does not exist")

        # count enabled modules
        if is_enabled:
            enabled_modules_count += 1

        # update or create relation
        PlanModule.objects.update_or_create(
            plan=plan,
            module=module,
            defaults={"is_enabled": is_enabled}
        )

    # 🔥 BUSINESS RULE: at least one module must be enabled
    if enabled_modules_count == 0:
        raise ValidationError("At least one module must be enabled")

    return True



