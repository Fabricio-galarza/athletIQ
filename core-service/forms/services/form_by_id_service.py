from django.db.models import Q
from forms.models import Form


def get_form_by_id(form_id, sport_id=None, user=None):

    try:
        form = Form.objects.get(id=form_id, is_active=True)
    except Form.DoesNotExist:
        raise ValueError("Form not found")

    # 🔥 validate access by plan
    if user:
        has_access = form.plan_forms.filter(
            is_enabled=True,
            plan__user_plans__user=user,
            plan__user_plans__is_active=True
        ).exists()

        if not has_access:
            raise ValueError("You do not have access to this form")

    # 🔥 filter fields by sport
    fields_qs = form.form_fields.filter(
        Q(sport_id=sport_id) | Q(sport__isnull=True)
    ).select_related(
        'field',
        'field__field_type'
    ).prefetch_related(
        'field__options'
    ).order_by('order')

    return {
        "id": form.id,
        "code": form.code,
        "name": form.name,
        "fields": fields_qs
    }