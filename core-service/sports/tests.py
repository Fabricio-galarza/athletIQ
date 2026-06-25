from django.test import TestCase
from users.models import User
from sports.models import Sport, UserSport


class SportTests(TestCase):
    def test_create_sport(self):
        sport = Sport.objects.create(name="Running")
        self.assertEqual(str(sport), "Running")
        self.assertTrue(sport.is_active)

    def test_sport_name_unique(self):
        Sport.objects.create(name="Crossfit")
        with self.assertRaises(Exception):
            Sport.objects.create(name="Crossfit")

    def test_sport_inactive_can_be_set(self):
        sport = Sport.objects.create(name="Swimming", is_active=False)
        self.assertFalse(sport.is_active)


class UserSportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="runner@test.com", password="pass1234")
        self.running = Sport.objects.create(name="Running")
        self.cycling = Sport.objects.create(name="Cycling")

    def test_assign_sport_to_user(self):
        us = UserSport.objects.create(user=self.user, sport=self.running)
        self.assertEqual(us.user, self.user)
        self.assertEqual(us.sport, self.running)

    def test_user_can_have_multiple_sports(self):
        UserSport.objects.create(user=self.user, sport=self.running)
        UserSport.objects.create(user=self.user, sport=self.cycling)
        self.assertEqual(self.user.user_sports.count(), 2)

    def test_str_representation(self):
        us = UserSport.objects.create(user=self.user, sport=self.running)
        self.assertEqual(str(us), "runner@test.com - Running")
