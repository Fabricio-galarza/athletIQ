from django.utils.timezone import now
from datetime import timedelta
from django.db import transaction

from payments.models import Payment
from plans.models import UserPlan


def process_payment_webhook(validated_data):

    external_id = validated_data.get("external_id")
    status_payment = validated_data.get("status")

    try:
        payment = Payment.objects.get(external_id=external_id)
    except Payment.DoesNotExist:
        raise ValueError("Payment not found")

    # idempotency control (but smarter)
    if payment.status == "paid" and UserPlan.objects.filter(
        user=payment.user,
        plan=payment.plan,
        is_active=True
    ).exists():
        return payment

    if status_payment == "paid":

        # atomic block (all or nothing)
        with transaction.atomic():

            user = payment.user
            plan = payment.plan

            # deactivate current plans
            UserPlan.objects.filter(
                user       = user,
                is_active  = True
            ).update(is_active=False,
                     updated_by = user
                     )
            
            payment.updated_by = user
            payment.save()

            # create new plan
            UserPlan.objects.create(
                user=user,
                plan=plan,
                start_date=now(),
                end_date=now() + timedelta(days=30),
                is_active=True,
                created_by = user
            )

            # 🔥 update payment LAST
            payment.status = "paid"
            payment.save()

    elif status_payment == "failed":

        payment.status = "failed"
        payment.save()

    return payment