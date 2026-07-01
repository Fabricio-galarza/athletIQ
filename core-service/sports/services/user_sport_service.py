from django.db import transaction

from sports.models import UserSport, Sport
from plans.models import UserPlan


def update_user_sports(user, sport_ids):

    # get active plan
    user_plan = UserPlan.objects.filter(
        user=user,
        is_active=True
    ).select_related("plan").first()

    if not user_plan:
        raise ValueError("User has no active plan")

    plan = user_plan.plan

    # get max sports from features
    max_sports = None

    features = plan.plan_features.select_related("feature").all()

    for pf in features:
        code = pf.feature.code

        if code.startswith("max_sports_"):
            try:
                max_sports = int(code.split("_")[-1])
                break
            except ValueError:
                continue

    # validate limit
    if max_sports and len(sport_ids) > max_sports:
        raise ValueError(f"Plan allows only {max_sports} sports")

    # get valid sports
    sports = Sport.objects.filter(id__in=sport_ids, is_active=True)

    with transaction.atomic():

        # remove current sports
        UserSport.objects.filter(user=user).delete()

        # create new relations with audit fields
        user_sports = [
            UserSport(
                user=user,
                sport=sport,
                created_by=user,   # audit
                updated_by=user    # audit
            )
            for sport in sports
        ]

        UserSport.objects.bulk_create(user_sports)

    return user_sports

def get_user_sports(user):

        # get user sports
        user_sports = UserSport.objects.filter(
            user = user
        ).select_related('sport')

        # return only sports
        return [us.sport for us in user_sports]