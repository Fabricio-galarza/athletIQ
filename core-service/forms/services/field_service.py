# forms/services/field_service.py
from django.db import transaction
from forms.models import Field, FieldType, DataType, FieldOPtion


@transaction.atomic
def create_field(validated_data, user=None):

    field_type_code = validated_data.pop("field_type_code")
    data_type_code = validated_data.pop("data_type_code", None)  # 🔥 Puede ser None
    options_data = validated_data.pop("options", [])
    ui_config = validated_data.pop("ui_config", {})  # 🔥 NEW

    # 🔥 UI-only field types list
    ui_only_types = ["section", "subheader", "dynamic_selects", "html", "divider", "spacer", "info_box"]

    # Get field type
    try:
        field_type = FieldType.objects.get(code=field_type_code)
    except FieldType.DoesNotExist:
        raise ValueError(f"Field type '{field_type_code}' not found")

    # Get data type (only for non UI-only fields)
    data_type = None
    if field_type_code not in ui_only_types:
        if not data_type_code:
            raise ValueError(f"Field type '{field_type_code}' requires a data_type")
        try:
            data_type = DataType.objects.get(code=data_type_code)
        except DataType.DoesNotExist:
            raise ValueError(f"Data type '{data_type_code}' not found")

    # Create field
    field = Field.objects.create(
        field_type=field_type,
        data_type=data_type,
        ui_config=ui_config,  # 🔥 NEW
        created_by=user,
        **validated_data,
    )

    # Create options if needed (for select, radio, checkbox)
    if field_type.code in ["select", "radio", "checkbox"]:
        if not options_data:
            raise ValueError("Selectable fields must include options")

        values = [opt["value"] for opt in options_data]
        labels = [opt.get("label", opt["value"]) for opt in options_data]
        orders = [opt.get("order", 0) for opt in options_data]

        if len(values) != len(set(values)):
            raise ValueError("Duplicate values not allowed")

        if len(labels) != len(set(labels)):
            raise ValueError("Duplicate labels not allowed")

        if len(orders) != len(set(orders)):
            raise ValueError("Duplicate order not allowed")

        for opt in options_data:
            FieldOPtion.objects.create(
                field=field,
                value=opt["value"],
                label=opt.get("label", opt["value"]),
                order=opt.get("order", 0),
                created_by=user
            )

    # 🔥 For dynamic_selects, options go in ui_config
    if field_type.code == "dynamic_selects" and options_data:
        # Merge options into ui_config
        field.ui_config["options"] = options_data
        field.save(update_fields=["ui_config"])

    return field