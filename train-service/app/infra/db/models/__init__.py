from app.infra.db.models.athlete import AthleteProfile, AthleteProfileValue
from app.infra.db.models.sport_profile import AthleteSportProfile, AthleteSportProfileValue
from app.infra.db.models.health import AthleteHealthProfile, AthleteHealthProfileValue
from app.infra.db.models.training_structure import AthleteTrainingStructure, AthleteTrainingStructureValue
from app.infra.db.models.goal import AthleteGoal, AthleteGoalValue
from app.infra.db.models.test_template import TestTemplate, TestTemplateBlock
from app.infra.db.models.session import TrainingSession, TrainingSessionBlock
from app.infra.db.models.plan import TrainingPlanPhase, TrainingPlanSession, TrainingPlan

__all__ = [
    "AthleteProfile",
    "AthleteProfileValue",
    "AthleteSportProfile",
    "AthleteSportProfileValue",
    "AthleteHealthProfile",
    "AthleteHealthProfileValue",
    "AthleteTrainingStructure",
    "AthleteTrainingStructureValue",
    "AthleteGoal",
    "AthleteGoalValue",
    "TestTemplate",
    "TestTemplateBlock",
    "TrainingSession",
    "TrainingSessionBlock",
    "TrainingPlan",
    "TrainingPlanPhase",
    "TrainingPlanSession"
]