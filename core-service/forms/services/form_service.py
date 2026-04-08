# forms/services/form_service.py
from django.db import transaction
from forms.models import Form
from modules.models import Module
from uuid import UUID

# creates a new form in the system
@transaction.atomic
def create_form(validated_data):
    module_code = validated_data.pop("module_code")
    
    try:
        module = Module.objects.get(code=module_code)
    except Module.DoesNotExist:
        raise ValueError("Module not found")
    
    validated_data.setdefault('is_active', False)
    form = Form.objects.create(module=module, **validated_data)
    return form


# Service to update a form
@transaction.atomic
def update_form(form_id, validated_data):
    # Handle both UUID and integer
    try:
        if isinstance(form_id, str) or isinstance(form_id, UUID):
            form = Form.objects.get(id=form_id)
        else:
            form = Form.objects.get(id=form_id)
    except (Form.DoesNotExist, ValueError):
        raise ValueError("Form not found")
    
    # Update only the fields provided
    for field, value in validated_data.items():
        setattr(form, field, value)
    
    form.save()
    return form


# Specific service to activate/deactivate a form
@transaction.atomic
def toggle_form_status(form_id, is_active):
    # Handle both UUID and integer
    try:
        if isinstance(form_id, str) or isinstance(form_id, UUID):
            form = Form.objects.get(id=form_id)
        else:
            form = Form.objects.get(id=form_id)
    except (Form.DoesNotExist, ValueError):
        raise ValueError("Form not found")
    
    form.is_active = is_active
    form.save()
    return form