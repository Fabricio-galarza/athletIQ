from django.db import transaction
from forms.models import Form, FormField, Field
from sports.models import Sport


# configure fields for a form (replace all configuration)
@transaction.atomic
def set_form_fields(form_id, fields_data):

    try:
        form = Form.objects.get(id=form_id)
    except Form.DoesNotExist:
        raise ValueError("Form not found")

    # 🚨 RULE: must have at least one field
    if not fields_data:
        raise ValueError("Form must have at least one field")

    # delete previous configuration (replace strategy)
    FormField.objects.filter(form=form).delete()

    created_fields = []

    for item in fields_data:

        # get field
        try:
            field = Field.objects.get(id=item["field_id"])
        except Field.DoesNotExist:
            raise ValueError(f"Field not found: {item['field_id']}")

        # get sport (optional)
        sport = None
        sport_id = item.get("sport_id")

        if sport_id:
            try:
                sport = Sport.objects.get(id=sport_id)
            except Sport.DoesNotExist:
                raise ValueError(f"Sport not found: {sport_id}")

        # 🔥 RULE: selectable fields must have options
        if field.field_type.code in ["select", "radio", "checkbox"]:
            if not field.options.exists():
                raise ValueError(
                    f"Field '{field.name}' must have options configured"
                )

        # create form field
        form_field = FormField.objects.create(
            form=form,
            field=field,
            sport=sport,
            label=item.get("label", field.name),
            is_required=item.get("is_required", False),
            order=item.get("order", 0)
        )

        created_fields.append(form_field)

    return created_fields