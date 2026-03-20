from django.db import models
import uuid


# Base model for all entities in the system
# centralizes:
# - UUID as primary key
# - audit timestamps
# - audit user tracking
class BaseModel(models.Model):

    # using UUID as standard id across the system
    # this helps with microservices and avoids exposing sequential ids
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # audit timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # user who created the record
    # can be null because some records may be created automatically by the system
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created"
    )

    # user who last updated the record
    updated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated"
    )

    class Meta:
        abstract = True  # prevents Django from creating a table for this model