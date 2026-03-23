from django.db.models.signals import pre_save
from django.dispatch import receiver
from .current_user import get_current_user
from common.models import BaseModel

@receiver(pre_save)
def set_audit_fields(sender, instance, **kwargs):
    # solo aplica a modelos que heredan de BaseModel
    if not issubclass(sender, BaseModel):
        return

    user = get_current_user()
    if not user:
        return

    # si es creación
    if not instance.pk:
        if not instance.created_by:
            instance.created_by = user

    # siempre actualiza updated_by
    instance.updated_by = user