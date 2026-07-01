from plans.models import Plan, PlanFeature, Feature, PlanModule
from modules.models import Module
from rest_framework.exceptions import ValidationError
from django.utils import timezone

# create a new subscription plan
def create_plan(validated_data, user = None):

    # create and return the plan
    plan = Plan.objects.create(
        **validated_data,
        created_by = user,
        created_at = timezone.now())

    return plan

# updates an existing plan
def update_plan(plan, validated_data, user = None):
    
    # update fields dynamically
    for attr, value in validated_data.items():
        setattr(plan, attr, value)

    # registering audit
    if user:
        plan.updated_by = user
    
    plan.updated_at = timezone.now()

    plan.save()

    return plan

# Sets fetures configuration for a given plan
def set_plan_features(plan, features_data, user = None):

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
            plan       = plan,
            feature    = feature,
            defaults   = {"is_enabled": is_enabled},
            created_by = user,
            created_at = timezone.now()
        )

    return True

# sets modules configuration for a given plan
def set_plan_modules(plan, modules_data, user = None):

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
            plan       = plan,
            module     = module,
            defaults   = {"is_enabled": is_enabled},
            created_by = user,
            created_at = timezone.now()
        )

    # 🔥 BUSINESS RULE: at least one module must be enabled
    if enabled_modules_count == 0:
        raise ValidationError("At least one module must be enabled")

    return True



