"""
Service layer for athlete profile management
"""

from uuid import UUID
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import func
import json

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

            if value is None:
                continue
            if not field_id:
                logger.warning(f"Skipping field '{field_name}': field_id is None, check form definition in X-User-Context")
                continue

            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, ensure_ascii=False)
            else:
                value_str = str(value)

            value_record = value_table(
                **{fk_field: fk_id},
                field_id=field_id,
                value=value_str,
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
        
        # Process athlete_profile form (main metrics)
        form = context.get_form("athlete_profile")
        if form and profile_data:
            sport_profile.form_id = form.id
            validated = form.validate_data(profile_data)
            self._save_form_values(AthleteProfileValue, "profile_id", profile.id, validated)
            self._save_form_values(AthleteSportProfileValue, "sport_profile_id", sport_profile.id, validated)
            missing = self._check_missing_fields(form, profile_data)
            all_missing_fields.extend(missing)
        
        # Process health data
        health_form = context.get_form("athlete_health_profile")
        if health_form and health_data:
            validated_health = health_form.validate_data(health_data)
            health_profile = AthleteHealthProfile(profile_id=profile.id, form_id=health_form.id)
            self.db.add(health_profile)
            self.db.flush()
            self._save_form_values(AthleteHealthProfileValue, "health_id", health_profile.id, validated_health)
            missing = self._check_missing_fields(health_form, health_data)
            all_missing_fields.extend(missing)
        
        # Process training structure
        structure_form = context.get_form("athlete_training_structure")
        if structure_form and training_structure_data:
            
            validated_structure = structure_form.validate_data(training_structure_data)
            
            # Deactivate existing active structure before creating new one
            existing_active = self.db.query(AthleteTrainingStructure).filter_by(
                profile_id=profile.id,
                sport_id=sport_id,
                is_active=True
            ).first()
            
            if existing_active:
                existing_active.is_active = False
                self.db.flush()
            
            training_structure = AthleteTrainingStructure(
                profile_id=profile.id,
                sport_id=sport_id,
                form_id=structure_form.id,
                is_active=True,
            )
            self.db.add(training_structure)
            self.db.flush()
            
            self._save_form_values(
                AthleteTrainingStructureValue, "structure_id", training_structure.id, validated_structure
            )

            missing = self._check_missing_fields(structure_form, training_structure_data)
            all_missing_fields.extend(missing)
        
        # Process goal data
        goal_form = context.get_form("athlete_goal")
        if goal_form and goal_data:
            validated_goal = goal_form.validate_data(goal_data)
            
            # Deactivate previous active goal
            self.db.query(AthleteGoal).filter_by(
                profile_id=profile.id, sport_id=sport_id, is_active=True
            ).update({"is_active": False})
            
            goal = AthleteGoal(
                profile_id=profile.id,
                sport_id=sport_id,
                form_id=goal_form.id,
                is_active=True
            )
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
    
    
    def get_goal_history(self, sport_id: str, context: UserContext) -> List[Dict[str, Any]]:
        """
        Get all goals (active and inactive) for a specific sport.
        
        Args:
            sport_id: Sport name (e.g., 'Running')
            context: User context with form definitions for field name mapping
        
        Returns:
            List of goals with their values and active status
        """
        # Get athlete profile
        profile = self.db.query(AthleteProfile).filter_by(
            user_id=self.user_id
        ).first()
        
        if not profile:
            return []
        
        # Get all goals for this sport
        goals = self.db.query(AthleteGoal).filter_by(
            profile_id=profile.id,
            sport_id=sport_id
        ).order_by(AthleteGoal.created_at.desc()).all()
        
        if not goals:
            return []
        
        # Build field_id to field_name mapping from context
        field_name_map = {}
        form = context.get_form("athlete_goal")
        
        if form:
            for field in form.fields:
                if field.id:
                    field_name_map[str(field.id)] = field.name
        
        result = []
        for goal in goals:
            # Get values for this goal
            values = self.db.query(AthleteGoalValue).filter_by(
                goal_id=goal.id
            ).all()
            
            # Convert field_id to field names using context mapping
            readable_values = {}
            for val in values:
                field_name = field_name_map.get(str(val.field_id), str(val.field_id))
                readable_values[field_name] = val.value
            
            result.append({
                "id": str(goal.id),
                "sport_id": goal.sport_id,
                "is_active": goal.is_active,
                "created_at": goal.created_at.isoformat() if goal.created_at else None,
                "updated_at": goal.updated_at.isoformat() if goal.updated_at else None,
                "values": readable_values,
            })
        
        return result
    

    def update_goal(self, goal_id: UUID, goal_data: Dict[str, Any], context: UserContext) -> Dict[str, Any]:
        """
        Update a specific goal.
        
        Args:
            goal_id: UUID of the goal to update
            goal_data: Dictionary with goal fields to update
            context: User context with form definitions
        
        Returns:
            Updated goal data
        """
        # Get the goal
        goal = self.db.query(AthleteGoal).filter_by(
            id=goal_id
        ).first()
        
        if not goal:
            raise NotFoundError("AthleteGoal", str(goal_id))
        
        # Verify ownership
        profile = self.db.query(AthleteProfile).filter_by(
            user_id=self.user_id
        ).first()
        
        if not profile or goal.profile_id != profile.id:
            raise ValidationError("Goal does not belong to this athlete")
        
        # Get form for validation
        form = context.get_form("athlete_goal")
        if not form:
            raise ValidationError("Form 'athlete_goal' not found in context")
        
        # Validate data (partial update allowed)
        validated = form.validate_data(goal_data, partial=True)
        
        updated_fields = []
        
        # Update or create values
        for field_name, field_data in validated.items():
            value = field_data["value"]
            field_id = field_data["field_id"]
            
            if value is None:
                continue
            
            updated_fields.append(field_name)
            
            # Check if value already exists
            existing = self.db.query(AthleteGoalValue).filter_by(
                goal_id=goal.id,
                field_id=field_id
            ).first()
            
            if existing:
                existing.value = str(value)
            else:
                self.db.add(AthleteGoalValue(
                    goal_id=goal.id,
                    field_id=field_id,
                    value=str(value),
                ))
        
        # Update timestamp
        goal.updated_at = func.now()
        
        self.db.commit()
        
        # Return updated goal
        return {
            "id": str(goal.id),
            "sport_id": goal.sport_id,
            "is_active": goal.is_active,
            "updated_fields": updated_fields,
            "message": "Goal updated successfully"
        }
    

    def create_goal(self, sport_id: str, goal_data: Dict[str, Any], context: UserContext) -> Dict[str, Any]:
        """
        Create a new goal for a sport.
        Deactivates any previously active goal for the same sport.
        
        Args:
            sport_id: Sport name (e.g., 'Running')
            goal_data: Dictionary with goal fields
            context: User context with form definitions
        
        Returns:
            Created goal data
        """
        # Get or create athlete profile
        profile = self._get_or_create_profile()
        
        # Get form for validation
        form = context.get_form("athlete_goal")
        if not form:
            raise ValidationError("Form 'athlete_goal' not found in context")
        
        # Validate data
        validated = form.validate_data(goal_data)
        
        # Deactivate previous active goal
        self.db.query(AthleteGoal).filter_by(
            profile_id=profile.id,
            sport_id=sport_id,
            is_active=True
        ).update({"is_active": False})
        
        # Create new goal
        goal = AthleteGoal(
            profile_id=profile.id,
            sport_id=sport_id,
            form_id=form.id,
            is_active=True,
        )
        self.db.add(goal)
        self.db.flush()
        
        # Save values
        for field_name, field_data in validated.items():
            value = field_data["value"]
            field_id = field_data["field_id"]
            
            if value is not None and field_id:
                self.db.add(AthleteGoalValue(
                    goal_id=goal.id,
                    field_id=field_id,
                    value=str(value),
                ))
        
        self.db.commit()
        
        # Return created goal
        return {
            "id": str(goal.id),
            "sport_id": sport_id,
            "is_active": True,
            "message": "Goal created successfully"
        }


    def get_equipment(self, sport_id: str, context: UserContext) -> Dict[str, Any]:
        """
        Get equipment for a specific sport.
        
        Args:
            sport_id: Sport name (e.g., 'Running')
            context: User context with form definitions for field name mapping
        
        Returns:
            Dictionary with equipment list
        """
        
        # Get athlete profile
        profile = self.db.query(AthleteProfile).filter_by(
            user_id=self.user_id
        ).first()
        
        if not profile:
            return {"has_equipment": False, "equipment": []}
        
        # Get training structure
        training_structure = self.db.query(AthleteTrainingStructure).filter_by(
            profile_id=profile.id,
            sport_id=sport_id,
            is_active=True
        ).first()
        
        if not training_structure:
            return {"has_equipment": False, "equipment": []}
        
        # Get field_id for 'equipment' from context
        equipment_field_id = None
        form = context.get_form("athlete_training_structure")
        
        if form:
            for field in form.fields:
                if field.name == "equipment":
                    equipment_field_id = field.id
                    break
        
        if not equipment_field_id:
            return {"has_equipment": False, "equipment": [], "error": "Equipment field not found in form"}
        
        # Find equipment value
        equipment_value = self.db.query(AthleteTrainingStructureValue).filter_by(
            structure_id=training_structure.id,
            field_id=equipment_field_id
        ).first()
        
        equipment_list = []
        if equipment_value and equipment_value.value:
            try:
                parsed = json.loads(equipment_value.value)
                if isinstance(parsed, list):
                    equipment_list = parsed
            except (json.JSONDecodeError, TypeError):
                # If not JSON, try to split by comma
                equipment_list = [e.strip() for e in equipment_value.value.split(',') if e.strip()]
        
        return {
            "has_equipment": len(equipment_list) > 0,
            "equipment": equipment_list,
            "structure_id": str(training_structure.id)
        }
    

    def update_equipment(self, sport_id: str, equipment_list: List[str], context: UserContext) -> Dict[str, Any]:
        """
        Update equipment for a specific sport.
        
        Args:
            sport_id: Sport name (e.g., 'Running')
            equipment_list: List of equipment items
            context: User context with form definitions
        
        Returns:
            Updated equipment data
        """
        
        # Get or create athlete profile
        profile = self._get_or_create_profile()
        
        # Get or create sport profile
        sport_profile = self._get_or_create_sport_profile(profile.id, sport_id)
        
        # Get or create training structure
        training_structure = self.db.query(AthleteTrainingStructure).filter_by(
            profile_id=profile.id,
            sport_id=sport_id,
            is_active=True
        ).first()
        
        if not training_structure:
            # Create a new training structure
            structure_form = context.get_form("athlete_training_structure")
            training_structure = AthleteTrainingStructure(
                profile_id=profile.id,
                sport_id=sport_id,
                form_id=structure_form.id if structure_form else None,
                is_active=True,
            )
            self.db.add(training_structure)
            self.db.flush()
        
        # Get field_id for 'equipment' from context
        equipment_field_id = None
        form = context.get_form("athlete_training_structure")
        
        if form:
            for field in form.fields:
                if field.name == "equipment":
                    equipment_field_id = field.id
                    break
        
        if not equipment_field_id:
            raise ValidationError("Equipment field not found in form")
        
        # Update or create equipment value
        existing = self.db.query(AthleteTrainingStructureValue).filter_by(
            structure_id=training_structure.id,
            field_id=equipment_field_id
        ).first()
        
        equipment_json = json.dumps(equipment_list, ensure_ascii=False)
        
        if existing:
            existing.value = equipment_json
        else:
            self.db.add(AthleteTrainingStructureValue(
                structure_id=training_structure.id,
                field_id=equipment_field_id,
                value=equipment_json,
            ))
        
        self.db.commit()
        
        return {
            "success": True,
            "sport_id": sport_id,
            "equipment": equipment_list,
            "message": "Equipment updated successfully"
        }