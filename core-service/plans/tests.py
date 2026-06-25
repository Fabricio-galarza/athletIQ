from django.test import TestCase
from decimal import Decimal
from users.models import User
from modules.models import Module
from plans.models import Plan, UserPlan, Feature, PlanFeature


class PlanTests(TestCase):
    def test_create_plan(self):
        plan = Plan.objects.create(name="Basic", price=Decimal("0.00"))
        self.assertEqual(str(plan), "Basic")
        self.assertTrue(plan.is_active)

    def test_plan_name_unique(self):
        Plan.objects.create(name="Pro", price=Decimal("9.99"))
        with self.assertRaises(Exception):
            Plan.objects.create(name="Pro", price=Decimal("9.99"))

    def test_plan_inactive(self):
        plan = Plan.objects.create(name="Legacy", price=Decimal("5.00"), is_active=False)
        self.assertFalse(plan.is_active)


class UserPlanTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="sub@test.com", password="pass1234")
        self.plan = Plan.objects.create(name="Elite", price=Decimal("29.99"))

    def test_assign_plan_to_user(self):
        up = UserPlan.objects.create(user=self.user, plan=self.plan)
        self.assertEqual(up.user, self.user)
        self.assertEqual(up.plan, self.plan)
        self.assertTrue(up.is_active)

    def test_user_plan_str(self):
        up = UserPlan.objects.create(user=self.user, plan=self.plan)
        self.assertEqual(str(up), "sub@test.com - Elite")

    def test_auto_renew_defaults_to_false(self):
        up = UserPlan.objects.create(user=self.user, plan=self.plan)
        self.assertFalse(up.auto_renew)


class PlanFeatureTests(TestCase):
    def setUp(self):
        self.plan = Plan.objects.create(name="Pro", price=Decimal("9.99"))
        self.module = Module.objects.create(name="Train", code="train")
        self.feature = Feature.objects.create(
            name="Adaptive Training", code="adaptive_training", module=self.module
        )

    def test_assign_feature_to_plan(self):
        pf = PlanFeature.objects.create(plan=self.plan, feature=self.feature)
        self.assertTrue(pf.is_enabled)
        self.assertEqual(str(pf), "Pro - adaptive_training")

    def test_plan_feature_unique_together(self):
        PlanFeature.objects.create(plan=self.plan, feature=self.feature)
        with self.assertRaises(Exception):
            PlanFeature.objects.create(plan=self.plan, feature=self.feature)
