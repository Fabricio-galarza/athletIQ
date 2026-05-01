"""
Service layer for athlete profile management (CU-TRAIN-01)
"""

from uuid import UUID
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session

from app.core.context import UserContext
from app.core.exceptions import NotFoundError, ValidationError
from app.infra.db.models.athlete import AthleteProfile, AthleteProfileValue
from app.infra.db.models.sport_profile import AthleteSportProfile, AthleteSportProfileValue
from app.infra.db.models.health import AthleteHealthProfile, AthleteHealthProfileValue
from app.infra.db.models.training_structure import AthleteTrainingStructure, AthleteTrainingStructureValue
from app.infra.db.models.goal import AthleteGoal, AthleteGoalValue
from app.services.sufficiency_service import SufficiencyService


class AthleteService:
    """Business logic for athlete profile management"""
    
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
    
    def _get_or_create_profile(self) -> AthleteProfile:
        """Get existing athlete profile or create a new one."""
        profile = self.db.query(AthleteProfile).filter_by(
            user_id=self.user_id
        ).first()
        
        if not profile:
            profile = AthleteProfile(user_id=self.user_id)
            self.db.add(profile)
            self.db.flush()
        
        return profile
    
    def _get_or_create_sport_profile(self, profile_id: UUID, sport_id: str) -> AthleteSportProfile:
        """Get existing sport profile or create a new one."""
        sport_profile = self.db.query(AthleteSportProfile).filter_by(
            profile_id=profile_id,
            sport_id=sport_id
        ).first()
        
        if not sport_profile:
            sport_profile = AthleteSportProfile(
                profile_id=profile_id,
                sport_id=sport_id,
            )
            self.db.add(sport_profile)
            self.db.flush()
        
        return sport_profile
    
    def _save_form_values(
        self, 
        value_table, 
        fk_field: str, 
        fk_id: UUID, 
        validated_data: Dict[str, Any]
    ) -> None:
        """Generic method to save form values to any value table."""
        for field_name, field_data in validated_data.items():
            value = field_data.get("value")
            field_id = field_data.get("field_id")
            
            if value is not None and field_id:
                value_record = value_table(
                    **{fk_field: fk_id},
                    field_id=field_id,
                    value=str(value),
                )
                self.db.add(value_record)
    
    def _check_missing_fields(
        self, 
        form, 
        data: Dict[str, Any]
    ) -> List[str]:
        """Check which required fields are missing from data."""
        missing = []
        if form:
            for field in form.fields:
                if field.required and field.name not in data:
                    missing.append(field.name)
        return missing
    
    async def create_sport_profile(
        self,
        sport_id: str,
        profile_data: Dict[str, Any],
        health_data: Dict[str, Any],
        training_structure_data: Dict[str, Any],
        goal_data: Dict[str, Any],
        context: UserContext,
    ) -> Tuple[UUID, UUID, bool, List[str]]:
        """Create complete sport profile for an athlete."""
        all_missing_fields = []
        
        profile = self._get_or_create_profile()
        sport_profile = self._get_or_create_sport_profile(profile.id, sport_id)
        
        form = context.get_form("athlete_profile")
        if form and profile_data:
            validated = form.validate_data(profile_data)
            self._save_form_values(AthleteProfileValue, "profile_id", profile.id, validated)
            self._save_form_values(AthleteSportProfileValue, "sport_profile_id", sport_profile.id, validated)
            missing = self._check_missing_fields(form, profile_data)
            all_missing_fields.extend(missing)
        
        health_form = context.get_form("athlete_health_profile")
        if health_form and health_data:
            validated_health = health_form.validate_data(health_data)
            health_profile = AthleteHealthProfile(profile_id=profile.id, form_id=health_form.id)
            self.db.add(health_profile)
            self.db.flush()
            self._save_form_values(AthleteHealthProfileValue, "health_id", health_profile.id, validated_health)
            missing = self._check_missing_fields(health_form, health_data)
            all_missing_fields.extend(missing)
        
        structure_form = context.get_form("athlete_training_structure")
        if structure_form and training_structure_data:
            validated_structure = structure_form.validate_data(training_structure_data)
            training_structure = AthleteTrainingStructure(profile_id=profile.id, sport_id=sport_id, form_id=structure_form.id)
            self.db.add(training_structure)
            self.db.flush()
            self._save_form_values(AthleteTrainingStructureValue, "structure_id", training_structure.id, validated_structure)
            missing = self._check_missing_fields(structure_form, training_structure_data)
            all_missing_fields.extend(missing)
        
        goal_form = context.get_form("athlete_goal")
        if goal_form and goal_data:
            validated_goal = goal_form.validate_data(goal_data)
            self.db.query(AthleteGoal).filter_by(
                profile_id=profile.id, sport_id=sport_id, is_active=True
            ).update({"is_active": False})
            goal = AthleteGoal(profile_id=profile.id, sport_id=sport_id, form_id=goal_form.id, is_active=True)
            self.db.add(goal)
            self.db.flush()
            self._save_form_values(AthleteGoalValue, "goal_id", goal.id, validated_goal)
            missing = self._check_missing_fields(goal_form, goal_data)
            all_missing_fields.extend(missing)
        
        self.db.commit()
        has_sufficient_data = len(all_missing_fields) == 0
        return profile.id, sport_profile.id, has_sufficient_data, all_missing_fields
    
    def get_sport_profile(self, sport_id: str) -> Dict[str, Any]:
        """Retrieve sport profile for an athlete."""
        profile = self.db.query(AthleteProfile).filter_by(user_id=self.user_id).first()
        if not profile:
            raise NotFoundError("AthleteProfile", str(self.user_id))
        
        sport_profile = self.db.query(AthleteSportProfile).filter_by(
            profile_id=profile.id, sport_id=sport_id
        ).first()
        if not sport_profile:
            raise NotFoundError("AthleteSportProfile", sport_id)
        
        values = self.db.query(AthleteSportProfileValue).filter_by(
            sport_profile_id=sport_profile.id
        ).all()
        return {
            "id": sport_profile.id,
            "sport_id": sport_profile.sport_id,
            "values": {str(v.field_id): v.value for v in values if v.value}
        }
    
    def get_complete_profile(self, sport_id: str) -> Dict[str, Any]:
        """Get complete athlete profile for a specific sport."""
        profile = self.db.query(AthleteProfile).filter_by(user_id=self.user_id).first()
        if not profile:
            raise NotFoundError("AthleteProfile", str(self.user_id))
        
        sport_profile = self.db.query(AthleteSportProfile).filter_by(
            profile_id=profile.id, sport_id=sport_id
        ).first()
        if not sport_profile:
            raise NotFoundError("AthleteSportProfile", sport_id)
        
        sport_values = self.db.query(AthleteSportProfileValue).filter_by(
            sport_profile_id=sport_profile.id
        ).all()
        
        health_profile = self.db.query(AthleteHealthProfile).filter_by(profile_id=profile.id).first()
        health_values = []
        if health_profile:
            health_values = self.db.query(AthleteHealthProfileValue).filter_by(
                health_id=health_profile.id
            ).all()
        
        training_structure = self.db.query(AthleteTrainingStructure).filter_by(
            profile_id=profile.id, sport_id=sport_id
        ).first()
        structure_values = []
        if training_structure:
            structure_values = self.db.query(AthleteTrainingStructureValue).filter_by(
                structure_id=training_structure.id
            ).all()
        
        goal = self.db.query(AthleteGoal).filter_by(
            profile_id=profile.id, sport_id=sport_id, is_active=True
        ).first()
        goal_values = []
        if goal:
            goal_values = self.db.query(AthleteGoalValue).filter_by(goal_id=goal.id).all()
        
        return {
            "profile": {"id": str(profile.id), "user_id": str(profile.user_id)},
            "sport_profile": {
                "id": str(sport_profile.id),
                "sport_id": sport_profile.sport_id,
                "values": {str(v.field_id): v.value for v in sport_values if v.value}
            },
            "health": {
                "has_data": health_profile is not None,
                "values": {str(v.field_id): v.value for v in health_values if v.value}
            },
            "training_structure": {
                "has_data": training_structure is not None,
                "values": {str(v.field_id): v.value for v in structure_values if v.value}
            },
            "active_goal": {
                "has_data": goal is not None,
                "values": {str(v.field_id): v.value for v in goal_values if v.value}
            }
        }
    
    def get_athlete_sports(self) -> List[str]:
        """Get all sports configured for the athlete."""
        profile = self.db.query(AthleteProfile).filter_by(user_id=self.user_id).first()
        if not profile:
            return []
        sport_profiles = self.db.query(AthleteSportProfile).filter_by(profile_id=profile.id).all()
        return [sp.sport_id for sp in sport_profiles]
    
    def update_sport_profile(
        self,
        sport_id: str,
        form_data: Dict[str, Dict[str, Any]],
        context: UserContext,
    ) -> Tuple[UUID, UUID, List[str], bool]:
        """
        Update specific fields of an athlete's sport profile.
        
        Args:
            sport_id: Sport name (e.g., 'Running')
            form_data: Dictionary of fields to update by form code
            context: User context with form definitions
        
        Returns:
            Tuple of (profile_id, sport_profile_id, updated_fields, has_sufficient_data)
        """
        updated_fields = []
        
        profile = self._get_or_create_profile()
        sport_profile = self._get_or_create_sport_profile(profile.id, sport_id)
        
        for form_code, data in form_data.items():
            if not data:
                continue
            
            form = context.get_form(form_code)
            if not form:
                raise ValidationError(f"Form '{form_code}' not found in context")
            
            # Use partial=True for PATCH updates
            validated = form.validate_data(data, partial=True)
            
            for field_name, field_data in validated.items():
                value = field_data["value"]
                field_id = field_data["field_id"]
                
                if value is None:
                    continue
                
                updated_fields.append(f"{form_code}.{field_name}")
                
                if form_code == "athlete_profile":
                    # Update athlete_profile_value
                    existing = self.db.query(AthleteProfileValue).filter_by(
                        profile_id=profile.id, field_id=field_id
                    ).first()
                    if existing:
                        existing.value = str(value)
                    else:
                        self.db.add(AthleteProfileValue(
                            profile_id=profile.id,
                            field_id=field_id,
                            value=str(value),
                        ))
                    
                    # Update sport_profile_value
                    existing_sport = self.db.query(AthleteSportProfileValue).filter_by(
                        sport_profile_id=sport_profile.id, field_id=field_id
                    ).first()
                    if existing_sport:
                        existing_sport.value = str(value)
                    else:
                        self.db.add(AthleteSportProfileValue(
                            sport_profile_id=sport_profile.id,
                            field_id=field_id,
                            value=str(value),
                        ))
                
                elif form_code == "athlete_health_profile":
                    health_profile = self.db.query(AthleteHealthProfile).filter_by(
                        profile_id=profile.id
                    ).first()
                    if not health_profile:
                        health_profile = AthleteHealthProfile(profile_id=profile.id)
                        self.db.add(health_profile)
                        self.db.flush()
                    
                    existing = self.db.query(AthleteHealthProfileValue).filter_by(
                        health_id=health_profile.id, field_id=field_id
                    ).first()
                    if existing:
                        existing.value = str(value)
                    else:
                        self.db.add(AthleteHealthProfileValue(
                            health_id=health_profile.id,
                            field_id=field_id,
                            value=str(value),
                        ))
                
                elif form_code == "athlete_training_structure":
                    training = self.db.query(AthleteTrainingStructure).filter_by(
                        profile_id=profile.id, sport_id=sport_id
                    ).first()
                    if not training:
                        training = AthleteTrainingStructure(profile_id=profile.id, sport_id=sport_id)
                        self.db.add(training)
                        self.db.flush()
                    
                    existing = self.db.query(AthleteTrainingStructureValue).filter_by(
                        structure_id=training.id, field_id=field_id
                    ).first()
                    if existing:
                        existing.value = str(value)
                    else:
                        self.db.add(AthleteTrainingStructureValue(
                            structure_id=training.id,
                            field_id=field_id,
                            value=str(value),
                        ))
                
                elif form_code == "athlete_goal":
                    goal = self.db.query(AthleteGoal).filter_by(
                        profile_id=profile.id, sport_id=sport_id, is_active=True
                    ).first()
                    if not goal:
                        goal = AthleteGoal(profile_id=profile.id, sport_id=sport_id, is_active=True)
                        self.db.add(goal)
                        self.db.flush()
                    
                    existing = self.db.query(AthleteGoalValue).filter_by(
                        goal_id=goal.id, field_id=field_id
                    ).first()
                    if existing:
                        existing.value = str(value)
                    else:
                        self.db.add(AthleteGoalValue(
                            goal_id=goal.id,
                            field_id=field_id,
                            value=str(value),
                        ))
        self.db.commit()
        
        sufficiency = SufficiencyService(self.db, self.user_id, sport_id, context)
        evaluation = sufficiency.evaluate()
        
        return profile.id, sport_profile.id, updated_fields, evaluation["has_sufficient_data"]