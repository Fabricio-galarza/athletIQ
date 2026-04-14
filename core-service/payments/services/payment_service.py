from payments.models import Payment
from plans.models import Plan

# Create plan payment
def create_payment(user, validated_data):

    plan_id = validated_data.get("plan_id")
    
    # get plan
    try:
        plan = Plan.objects.get(id=plan_id)
    except Plan.DoesNotExist:
        raise ValueError("PLAN_NOT_FOUND")
    
    # create paymente intent
    payment = Payment.objects.create(
        user       = user,
        plan       = plan,
        amount     = plan.price,
        status     = "pending",
        created_by = user
    )

    # TEMP: use internal id as a external_id (for testing webhook)
    payment.external_id = payment.id
    payment.save()

    return payment