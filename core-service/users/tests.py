from django.test import TestCase
from django.core.exceptions import ValidationError as DjangoValidationError
from users.models import User, Profile, ProfileType, UserProfile


class UserManagerTests(TestCase):
    def test_create_user_with_email(self):
        user = User.objects.create_user(email="athlete@test.com", password="pass1234")
        self.assertEqual(user.email, "athlete@test.com")
        self.assertTrue(user.check_password("pass1234"))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="pass1234")

    def test_create_superuser(self):
        user = User.objects.create_superuser(email="admin@test.com", password="admin1234")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_email_is_unique(self):
        User.objects.create_user(email="dup@test.com", password="pass1234")
        with self.assertRaises(Exception):
            User.objects.create_user(email="dup@test.com", password="other1234")

    def test_email_is_normalized(self):
        user = User.objects.create_user(email="Athlete@TEST.COM", password="pass1234")
        self.assertEqual(user.email, "Athlete@test.com")


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="prof@test.com", password="pass1234")

    def test_create_profile(self):
        profile = Profile.objects.create(
            user=self.user,
            first_name="Juan",
            last_name="Perez",
            birth_date="1995-06-15",
            gender="male",
        )
        self.assertEqual(profile.user, self.user)
        self.assertEqual(str(profile), "Juan Perez")

    def test_profile_optional_fields(self):
        profile = Profile.objects.create(user=self.user, first_name="Ana", last_name="Lopez")
        self.assertIsNone(profile.birth_date)
        self.assertIsNone(profile.gender)

    def test_profile_is_one_to_one(self):
        Profile.objects.create(user=self.user, first_name="X", last_name="Y")
        with self.assertRaises(Exception):
            Profile.objects.create(user=self.user, first_name="Dup", last_name="Dup")


class ProfileTypeTests(TestCase):
    def test_create_profile_type(self):
        pt = ProfileType.objects.create(name="athlete")
        self.assertEqual(str(pt), "athlete")

    def test_profile_type_name_unique(self):
        ProfileType.objects.create(name="coach")
        with self.assertRaises(Exception):
            ProfileType.objects.create(name="coach")


class UserProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="up@test.com", password="pass1234")
        self.athlete_type = ProfileType.objects.create(name="athlete")
        self.coach_type = ProfileType.objects.create(name="coach")

    def test_assign_role_to_user(self):
        up = UserProfile.objects.create(user=self.user, profile_type=self.athlete_type)
        self.assertEqual(up.user, self.user)
        self.assertEqual(up.profile_type, self.athlete_type)

    def test_user_can_have_multiple_roles(self):
        UserProfile.objects.create(user=self.user, profile_type=self.athlete_type)
        UserProfile.objects.create(user=self.user, profile_type=self.coach_type)
        self.assertEqual(self.user.user_profiles.count(), 2)
