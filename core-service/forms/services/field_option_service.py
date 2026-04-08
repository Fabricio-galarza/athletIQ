from django.db import transaction
from forms.models import Field, FieldOPtion


@transaction.atomic
def set_field_options(field_id, options_data):

    try:
        field = Field.objects.get(id=field_id)
    except Field.DoesNotExist:
        raise ValueError("Field not found")

    # RULE: only selectable fields
    if field.field_type.code not in ["select", "radio", "checkbox"]:
        raise ValueError("Field does not support options")

    if not options_data:
        raise ValueError("Options cannot be empty")

    values = [opt["value"] for opt in options_data]
    labels = [opt.get("label", opt["value"]) for opt in options_data]
    orders = [opt.get("order", 0) for opt in options_data]

    # duplicate values
    if len(values) != len(set(values)):
        raise ValueError("Duplicate option values are not allowed")

    # duplicate labels
    if len(labels) != len(set(labels)):
        raise ValueError("Duplicate option labels are not allowed")

    # duplicate order
    if len(orders) != len(set(orders)):
        raise ValueError("Duplicate order values are not allowed")

    # replace strategy
    FieldOPtion.objects.filter(field=field).delete()

    created_options = []

    for opt in options_data:

        option = FieldOPtion.objects.create(
            field=field,
            value=opt["value"],
            label=opt.get("label", opt["value"]),
            order=opt.get("order", 0)
        )

        created_options.append(option)

    return created_options