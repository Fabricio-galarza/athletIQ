from django.db import models
from common.models import BaseModel


# defines a dynamic form in the system
# examples: athlete registration, fitness assessment
class Form(BaseModel):

    name = models.CharField(max_length=100)

    code = models.CharField(max_length=100, unique=True)

    # indicates if the form is active
    is_active = models.BooleanField(default=True)

    # module where the form belongs (core, train, etc.)
    module = models.ForeignKey(
        'modules.Module',
        on_delete=models.CASCADE,
        related_name='forms'
    )

    def __str__(self):
        return self.name

    
# defines daabase data types (varchar, integer, boolean, date, etc)
class DataType(BaseModel):

    # internarl code (varchar, integer, boolean)
    code = models.CharField(max_length=50, unique=True)

    # Human readable name
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    

# defines UI field types (how the field is rendered in frontend)
class FieldType(BaseModel):

    # internar code (text, number, select, radio, checck, etc)
    code = models.CharField(max_length=50, unique=True)

    # Human readeble name
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    

# defines a field type that can be used in forms
# examples: text, number, select, date
class Field(BaseModel):

    # internal name used in code (snake_case recomendado)
    name = models.CharField(max_length=100, unique=True)

    # UI behavior (text, select, number, etc.)
    field_type = models.ForeignKey(
        FieldType,
        on_delete=models.PROTECT,
        related_name='fields'
    )

    # database data type (integer, varchar, etc.)
    data_type = models.ForeignKey(
        DataType,
        on_delete=models.PROTECT,
        related_name='fields'
    )

    def __str__(self):
        return self.name

# options for selectable fields (select, radio, checkbox)
class FieldOPtion(BaseModel):

    #Feild realtion
    field = models.ForeignKey(
        Field,
        on_delete    = models.CASCADE,
        related_name = "options"
    )

    # value stores BD
    value = models.CharField(max_length=100)

    # label shown ot user
    label = models.CharField(max_length=100)

    order = models.IntegerField()

    def __str__(self):
        return f"{self.field.name} - {self.label}"
    

# configuration of a field inside a form
class FormField(BaseModel):

    # form where the field belongs
    form = models.ForeignKey(
        Form,
        on_delete=models.CASCADE,
        related_name='form_fields'
    )

    # reusable field definition
    field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        related_name='form_fields'
    )

    # label shown in UI (can override field name)
    label = models.CharField(max_length=100)

    # indicates if the field is required
    is_required = models.BooleanField(default=False)

    # order inside the form
    order = models.IntegerField()

    # 🔥 sport-specific configuration (optional)
    sport = models.ForeignKey(
        'sports.Sport',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='form_fields'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['form', 'field', 'sport'],
                name='unique_form_field_sport'
            ),
            models.UniqueConstraint(
                fields=['order', 'field'],
                name='unique_order_field'
            ),
        ]

    def __str__(self):
        return f"{self.form.code} - {self.field.name}"
    
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

    class Meta:
        unique_together = ('sport', 'form')

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