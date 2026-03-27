from django.db import models
from common.models import BaseModel


# defines a dynamic form in the system
# examples: athlete registration, fitness assessment
class Form(BaseModel):

    name = models.CharField(max_length=100)

    code = models.CharField(max_length=100, unique=True)

    # module where the form belongs (core, train, etc.)
    module = models.CharField(max_length=50)

    # indicates if the form is active
    is_active = models.BooleanField(default=True)

    module = models.ForeignKey(
        'modules.Module',
        on_delete=models.CASCADE,
        related_name='forms'
    )

    def __str__(self):
        return self.name
    
# defines a field type that can be used in forms
# examples: text, number, select, date
class Field(BaseModel):

    # field name (for display)
    name = models.CharField(max_length=100)

    # type of field (used by frontend to render input)
    # examples: text, number, select, date
    type = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.name} ({self.type})"
    

# defines which fields belong to a form
# and how they behave inside the form
class FormField(BaseModel):

    form = models.ForeignKey(
        Form,
        on_delete=models.CASCADE,
        related_name='form_fields'
    )

    field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        related_name='form_fields'
    )

    # indicates if the field is required
    is_required = models.BooleanField(default=False)

    # order of the field in the form
    order = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.form.name} - {self.field.name}"
    
# defines which forms are associated with each sport
# this allows customizing forms per sport (e.g. running vs crossfit)
class SportForm(BaseModel):

    sport = models.ForeignKey(
        'sports.Sport',
        on_delete=models.CASCADE,
        related_name='sport_forms'
    )

    form = models.ForeignKey(
        Form,
        on_delete=models.CASCADE,
        related_name='sport_forms'
    )

    def __str__(self):
        return f"{self.sport.name} - {self.form.name}"
    
class SportField(BaseModel):

    # sport this configuration belongs to
    sport = models.ForeignKey(
        'sports.Sport',
        on_delete=models.CASCADE,
        related_name='sport_fields'
    )

    # base field definition
    field = models.ForeignKey(
        'forms.Field',
        on_delete=models.CASCADE,
        related_name='sport_fields'
    )

    # label override for this sport
    label = models.CharField(max_length=100)

    # whether the field is required in this sport
    is_required = models.BooleanField(default=False)

    # order for UI rendering
    order = models.IntegerField(default=0)

    # optional: visibility control
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('sport', 'field')
        ordering = ['order']

    def __str__(self):
        return f"{self.sport.name} - {self.field.code}"