from django.db.models import Q
from forms.models import Form


def get_forms(module_code=None, sport_id=None, user=None):

    forms_qs = Form.objects.filter(is_active=True)

    if module_code:
        forms_qs = forms_qs.filter(module__code=module_code)

    if user:
        forms_qs = forms_qs.filter(
            plan_forms__is_enabled=True,
            plan_forms__plan__user_plans__user=user,
            plan_forms__plan__user_plans__is_active=True
        ).distinct()

    return forms_qs