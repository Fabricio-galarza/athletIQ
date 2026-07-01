from django.db import models
from common.models import BaseModel
from django.utils import timezone


# defines subscription plans available in the system
# this is what users can purchase
class Plan(BaseModel):

    # plan name (Basic, Pro, Elite, etc.)
    name = models.CharField(max_length=100, unique=True)

    # optional description of the plan
    description = models.TextField(null=True, blank=True)

    # plan price
    price = models.DecimalField(max_digits=10, decimal_places=2)

    # indicates if the plan is currently available
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
# represents a user's subscription to a plan
# this model handles:
# - active plan
# - plan history
# - upgrades / downgrades
class UserPlan(BaseModel):

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='user_plans'
    )

    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name='user_plans'
    )

    # when the plan starts
    start_date = models.DateField(default=timezone.now)

    # when the plan ends (null = active or lifetime)
    end_date = models.DateTimeField(null=True, blank=True)

    # indicates if this is the current active plan
    is_active = models.BooleanField(default=True)

    # Automatic renewal, future implementation
    auto_renew = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} - {self.plan.name}"
    
# defines a system capability or functionality
# examples:
# - create_training_plan
# - advanced_metrics
# - adaptive_training
class Feature(BaseModel):

    # human-readable name
    name = models.CharField(max_length=100)

    # unique identifier used in code
    code = models.CharField(max_length=100, unique=True)

    module = models.ForeignKey(
        'modules.Module',
        on_delete=models.CASCADE,
        related_name='features'
    )

    def __str__(self):
        return self.name
    
# defines which features are enabled for each plan
# this is where we control system capabilities per subscription
class PlanFeature(BaseModel):

    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name='plan_features'
    )

    feature = models.ForeignKey(
        Feature,
        on_delete=models.CASCADE,
        related_name='plan_features'
    )

    # indicates if the feature is enabled for the plan
    is_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ('plan', 'feature')

    def __str__(self):
        return f"{self.plan.name} - {self.feature.code}"
    
# defines which modules are enabled for each plan
# this controls access to system modules per subscription
class PlanModule(BaseModel):

    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name='plan_modules'
    )

    module = models.ForeignKey(
        'modules.Module',
        on_delete=models.CASCADE,
        related_name='plan_modules'
    )

    # indicates if the module is enabled for the plan
    is_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ('plan', 'module')

    def __str__(self):
        return f"{self.plan.name} - {self.module.code}"
    
# defines which forms are enabled for each plan
# this controls what data users can input per subscription
class PlanForm(BaseModel):

    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name='plan_forms'
    )

    form = models.ForeignKey(
        'forms.Form',
        on_delete=models.CASCADE,
        related_name='plan_forms'
    )

    # indicates if the form is enabled for the plan
    is_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ('plan', 'form')

    def __str__(self):
        return f"{self.plan.name} - {self.form.name}"