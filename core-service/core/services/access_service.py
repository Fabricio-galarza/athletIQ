import logging

logger = logging.getLogger(__name__)


# returns full access context for a user based on their active plan
def get_user_access_context(user):

    # cache access context during request lifecycle
    if hasattr(user, "_access_context"):
        return user._access_context

    # get active plan
    user_plan = user.user_plans.filter(is_active=True)\
        .select_related('plan')\
        .first()
    
    logger.info(f"Building access context for user {user.id}")

    if not user_plan:
        context = {
            "plan": None,
            "plan_id": None,
            "modules": set(),
            "features": set(),
            "forms": set(),
        }

        user._access_context = context
        return context

    plan = user_plan.plan

    # modules enabled
    modules_qs = plan.plan_modules.filter(is_enabled=True)\
        .select_related('module')

    module_ids = [pm.module.id for pm in modules_qs]
    module_codes = {pm.module.code for pm in modules_qs}

    # features enabled AND module enabled
    features_qs = plan.plan_features.filter(
        is_enabled=True,
        feature__module_id__in=module_ids
    ).select_related('feature')

    feature_codes = {pf.feature.code for pf in features_qs}

    # forms enabled AND module enabled
    forms_qs = plan.plan_forms.filter(
        is_enabled=True,
        form__module_id__in=module_ids
    ).select_related('form')

    form_codes = {pf.form.code for pf in forms_qs}

    context = {
        "plan": plan.name,
        "plan_id": str(plan.id),
        "modules": module_codes,
        "features": feature_codes,
        "forms": form_codes,
    }

    # cache context in user instance
    user._access_context = context

    return context

#  validating if user has feature available
def user_has_feature(user, feature_code):
    return user_has_access(user, "features", feature_code)

#  Validating if user has module available
def user_has_module(user, module_code):
    return user_has_access(user, "modules", module_code)

# checks if a user has access to a specific form based on their plan

def user_has_form(user, form_code):
    return user_has_access(user, "forms", form_code)

# generic access validator
def user_has_access(user, access_type, code):

    context = get_user_access_context(user)

    return code in context.get(access_type, set())