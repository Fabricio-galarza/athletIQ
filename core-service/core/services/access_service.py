import logging
from permissions.models import Role
from sports.models import Sport
from forms.models import Form

logger = logging.getLogger(__name__)


def get_user_access_context(user):
    """
    Returns full access context for a user based on their active plan.
    Includes roles, sports, and forms with their fields.
    """
    # cache access context during request lifecycle
    if hasattr(user, "_access_context"):
        return user._access_context

    logger.info(f"Building access context for user {user.id}")

    # Get user roles
    roles = list(Role.objects.filter(user_roles__user=user).values_list('name', flat=True))
    
    # Get user sports (by name)
    sports = list(Sport.objects.filter(user_sports__user=user).values_list('name', flat=True))

    # Get active plan
    user_plan = user.user_plans.filter(is_active=True)\
        .select_related('plan')\
        .first()

    if not user_plan:
        context = {
            "user_id": str(user.id),
            "email": user.email,
            "roles": roles,
            "sports": sports,
            "plan": None,
            "plan_id": None,
            "modules": [],
            "features": [],
            "forms": [],
        }
        user._access_context = context
        return context

    plan = user_plan.plan

    # modules enabled
    modules_qs = plan.plan_modules.filter(is_enabled=True)\
        .select_related('module')

    module_ids = [pm.module.id for pm in modules_qs]
    module_codes = [pm.module.code for pm in modules_qs]

    # features enabled AND module enabled
    features_qs = plan.plan_features.filter(
        is_enabled=True,
        feature__module_id__in=module_ids
    ).select_related('feature')

    feature_codes = [pf.feature.code for pf in features_qs]

    # forms enabled AND module enabled, with their fields
    forms_qs = plan.plan_forms.filter(
        is_enabled=True,
        form__module_id__in=module_ids
    ).select_related('form')

    forms = []
    for pf in forms_qs:
        form = pf.form
        
        # Get fields for this form (ordered)
        form_fields = form.form_fields.all().order_by('order').select_related('field')
        
        fields = []
        for ff in form_fields:
            field = ff.field
            
            # Build field structure
            field_data = {
                "id": str(field.id),
                "name": field.name,
                "label": ff.label or field.label,
                "type": field.field_type.code,
                "required": ff.is_required,
                "order": ff.order,
            }
            
            # Add options for select/radio/checkbox fields
            if field.field_type.code in ['select', 'radio', 'checkbox']:
                options = field.options.all().order_by('order')
                field_data["options"] = [
                    {
                        "value": opt.value,
                        "label": opt.label or opt.value,
                        "order": opt.order,
                    }
                    for opt in options
                ]
            
            fields.append(field_data)
        
        forms.append({
            "id": str(form.id),
            "name": form.name,
            "code": form.code,
            "module": form.module.name if form.module else None,
            "fields": fields,
        })

    context = {
        "user_id": str(user.id),
        "email": user.email,
        "roles": roles,
        "sports": sports,
        "plan": plan.name,
        "plan_id": str(plan.id),
        "modules": module_codes,
        "features": feature_codes,
        "forms": forms,
    }

    # cache context in user instance
    user._access_context = context

    return context


# Helper functions (same as before)
def user_has_feature(user, feature_code):
    return user_has_access(user, "features", feature_code)


def user_has_module(user, module_code):
    return user_has_access(user, "modules", module_code)


def user_has_form(user, form_code):
    return user_has_access(user, "forms", form_code)


def user_has_role(user, role_name):
    context = get_user_access_context(user)
    return role_name in context.get("roles", [])


def user_has_sport(user, sport_name):
    context = get_user_access_context(user)
    return sport_name in context.get("sports", [])


def user_has_access(user, access_type, code):
    context = get_user_access_context(user)
    if access_type == "forms":
        # For forms, check by code
        return any(form.get("code") == code for form in context.get("forms", []))
    return code in context.get(access_type, [])