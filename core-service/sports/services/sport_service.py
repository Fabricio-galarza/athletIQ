from sports.models import Sport

def get_available_sports(user):
    
    # get only active sports
    sports_qs = Sport.objects.filter(is_active=True)

    return sports_qs