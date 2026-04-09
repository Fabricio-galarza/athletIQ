from django.db import models

from common.models import BaseModel


class Payment(BaseModel):

    # payment status options
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    # billing Type options (future ready)
    BILLING_TYPE_CHOISES = [
        ("one", "One Time"),
        ("suscription", "Subscription"),
    ]

    # user who pays
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="payments"
    )

    # plan being purchased
    plan = models.ForeignKey(
        "plans.Plan",
        on_delete=models.CASCADE,
        related_name="payments"
    )

    # payment status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    #external provider id (stripe, payu, etc)
    external_id = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    # amount to pay
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    #billing type (future use)
    billing_type = models.CharField(
        max_length=20,
        choices=BILLING_TYPE_CHOISES,
        default="on_time"
    )

    def __str__(self):
        return f"{self.user} - {self.plan} - {self.status}"
