from plans.models import PlanForm, PlanModule
from forms.models import Form
from rest_framework.exceptions import ValidationError


def set_plan_forms(plan, forms_data):
    # Loop through input data
    for item in forms_data:
        
        # Extract fields
        form_id = item.get("form_id")
        form_code = item.get("code")
        is_enabled = item.get("is_enabled")

        try:
            # Fetch form
            form = Form.objects.get(id=form_id)
        except Form.DoesNotExist:
            # Form not found
            raise ValidationError(f"Form {form_id} does not exist")

        # Ensure module is enabled in plan
        if not PlanModule.objects.filter(
            plan=plan,
            module=form.module,
            is_enabled=True
        ).exists():
            raise ValidationError(
                f"Module {form.module.code} is not enabled for this plan"
            )

        # Create or update relation
        PlanForm.objects.update_or_create(
            plan=plan,
            form=form,
            defaults={"is_enabled": is_enabled}
        )

    # Success
    return True