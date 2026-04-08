from django.db import transaction
from forms.models import Field, FieldType, DataType, FieldOPtion


@transaction.atomic
def create_field(validated_data):

    field_type_code = validated_data.pop("field_type_code")
    data_type_code = validated_data.pop("data_type_code")
    options_data = validated_data.pop("options", [])

    # get field type
    try:
        field_type = FieldType.objects.get(code=field_type_code)

    except FieldType.DoesNotExist:
        raise ValueError("Field type not found")
    
    # get data type
    try:
        data_type = DataType.objects.get(code=data_type_code)
    except DataType.DoesNotExist:
        raise ValueError("Data type not found")

    # create field
    field = Field.objects.create(
        field_type=field_type,
        data_type=data_type,
        **validated_data
    )

    # create options if needed
    if field_type.code in ["select", "radio", "checkbox"]:

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
                order=opt.get("order", 0)
            )

    return field