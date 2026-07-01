from rest_framework import serializers
from sports.models import Sport, UserSport

class UserSportSerializer(serializers.Serializer):

    # list of sports ids
    sports = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False
    )

    def validate_sports(self, value):

        # remove duplicates
        unique_sports = list(set(value))

        # validate all sports exists and are active
        sports_qs = Sport.objects.filter(
            id__in=unique_sports,
            is_active=True
        )

        if len(unique_sports) != sports_qs.count():
            raise serializers.ValidationError(
                "one or more sports are invalid or inactive"
            )

        return unique_sports
    
    