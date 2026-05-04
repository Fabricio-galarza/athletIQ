"""
CU-TRAIN-01-HU-05: Automatic data sufficiency evaluation.
CU-TRAIN-01-HU-06: Find appropriate test template for athlete.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.context import UserContext
from app.infra.db.models.athlete import AthleteProfile
from app.infra.db.models.sport_profile import AthleteSportProfileValue


class SufficiencyService:
    """
    Evaluates if athlete has sufficient data based on Core forms.
    Finds appropriate test template based on athlete profile.
    """
    
    def __init__(self, db: Session, user_id: str, sport_id: str, context: UserContext):
        """Initialize service with database session and user context."""
        self.db = db
        self.user_id = user_id
        self.sport_id = sport_id
        self.context = context
    
    def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate data sufficiency using cached context form.
        
        Returns:
            Dict with:
            - has_sufficient_data: bool
            - missing_required_fields: list
            - completion_score: int (0-100)
            - requires_test: bool
            - total_required_fields: int
            - completed_required_fields: int
            - test_template: dict or None
        """
        # Get form from cached context
        form = self.context.get_form("athlete_profile")
        
        if not form:
            return {
                "has_sufficient_data": False,
                "missing_required_fields": [],
                "completion_score": 0,
                "requires_test": True,
                "total_required_fields": 0,
                "completed_required_fields": 0,
                "message": "Form not found in context",
                "test_template": None
            }
        
        # Get required fields from form definition
        required_fields = [f.name for f in form.fields if f.required]
        
        # Get existing field values from database
        existing_fields = self._get_existing_field_names()
        
        # Find missing required fields
        missing = [f for f in required_fields if f not in existing_fields]
        
        # Calculate completion score
        total = len(required_fields)
        completed = total - len(missing)
        score = int((completed / total) * 100) if total > 0 else 100
        
        requires_test = len(missing) > 0
        
        # Find test template if needed
        test_template = None
        if requires_test:
            test_template = self._find_test_template()
        
        return {
            "has_sufficient_data": not requires_test,
            "missing_required_fields": missing,
            "completion_score": score,
            "requires_test": requires_test,
            "total_required_fields": total,
            "completed_required_fields": completed,
            "test_template": test_template,
        }
    
    def _get_existing_field_names(self) -> set:
        """Get set of field IDs that already have values."""
        existing = set()
        
        profile = self.db.query(AthleteProfile).filter_by(
            user_id=self.user_id
        ).first()
        
        if not profile:
            return existing
        
        query = text("""
            SELECT field_id FROM train.athlete_sport_profile_value 
            WHERE sport_profile_id IN (
                SELECT id FROM train.athlete_sport_profile WHERE profile_id = :profile_id
            )
        """)
        
        result = self.db.execute(query, {"profile_id": profile.id}).fetchall()
        
        for row in result:
            existing.add(str(row[0]))
        
        return existing
    
    def _get_athlete_data(self) -> Dict[str, Any]:
        """
        Get athlete data from database for template matching.
        
        Reads:
        - level (from profile)
        - age_range (converted to numeric age for template matching)
        - gender
        - health_status
        
        Returns:
            Dict with level, age, gender, health_status
        """
        # Default values
        athlete_data = {
            "level": "intermediate",
            "age": 30,  # Default age for calculation
            "gender": "any",
            "health_status": "healthy"
        }
        
        # Get athlete profile
        profile = self.db.query(AthleteProfile).filter_by(
            user_id=self.user_id
        ).first()
        
        if not profile:
            return athlete_data
        
        # Get field_id to name mapping from context
        form = self.context.get_form("athlete_profile")
        field_name_to_id = {}
        field_id_to_name = {}
        
        if form:
            for field in form.fields:
                if field.id:
                    field_id_to_name[str(field.id)] = field.name
                    field_name_to_id[field.name] = str(field.id)
        
        # Get sport profile values
        query = text("""
            SELECT aspv.field_id, aspv.value
            FROM train.athlete_sport_profile_value aspv
            JOIN train.athlete_sport_profile asp ON aspv.sport_profile_id = asp.id
            WHERE asp.profile_id = :profile_id
        """)
        
        result = self.db.execute(query, {"profile_id": profile.id}).fetchall()
        
        # Age range to numeric mapping
        age_range_map = {
            "0-18": 16,
            "18-25": 22,
            "26-35": 30,
            "36-45": 40,
            "46-55": 50,
            "55+": 60,
        }
        
        for row in result:
            field_id = str(row[0])
            value = row[1]
            
            field_name = field_id_to_name.get(field_id)
            
            if field_name == "level":
                athlete_data["level"] = value if value else "intermediate"
            elif field_name == "age_range":
                athlete_data["age"] = age_range_map.get(value, 30)
            elif field_name == "gender":
                athlete_data["gender"] = value if value else "any"
            elif field_name == "health_status":
                athlete_data["health_status"] = value if value else "healthy"
        
        return athlete_data
    
    def _find_test_template(self) -> Optional[Dict[str, Any]]:
        """
        Find the most appropriate test template for the athlete.
        
        Matches based on:
        - Sport
        - Level
        - Age range
        - Gender
        - Health status
        """
        athlete_data = self._get_athlete_data()
        
        print("=" * 50)
        print(f"🔍 Buscando template para:")
        print(f"   sport: {self.sport_id}")
        print(f"   level: {athlete_data.get('level')}")
        print(f"   age: {athlete_data.get('age')}")
        print(f"   gender: {athlete_data.get('gender')}")
        print(f"   health_status: {athlete_data.get('health_status')}")
        print("=" * 50)
        
        query = text("""
            SELECT 
                tt.id,
                tt.code,
                tt.name,
                tt.description,
                tt.duration_minutes,
                tt.sport,
                tt.level
            FROM train.test_template tt
            WHERE tt.sport = :sport
              AND tt.level = :level
              AND tt.is_active = TRUE
              AND (tt.min_age IS NULL OR tt.min_age <= :age)
              AND (tt.max_age IS NULL OR tt.max_age >= :age)
              AND (tt.gender = :gender OR tt.gender = 'any')
              AND (tt.health_status = :health_status OR tt.health_status = 'any')
            ORDER BY tt.priority ASC
            LIMIT 1
        """)
        
        result = self.db.execute(query, {
            "sport": self.sport_id,
            "level": athlete_data.get("level", "intermediate"),
            "age": athlete_data.get("age", 30),
            "gender": athlete_data.get("gender", "any"),
            "health_status": athlete_data.get("health_status", "healthy")
        }).first()
        
        if not result:
            return self._get_fallback_template()
        
        # Get blocks for this template
        blocks_query = text("""
            SELECT 
                block_order,
                block_type,
                duration_minutes,
                intensity,
                instructions
            FROM train.test_template_block
            WHERE template_id = :template_id
            ORDER BY block_order ASC
        """)
        
        blocks = self.db.execute(blocks_query, {"template_id": result.id}).fetchall()
        
        return {
            "id": str(result.id),
            "code": result.code,
            "name": result.name,
            "description": result.description,
            "duration_minutes": result.duration_minutes,
            "sport": result.sport,
            "level": result.level,
            "blocks": [
                {
                    "block_order": b.block_order,
                    "block_type": b.block_type,
                    "duration_minutes": b.duration_minutes,
                    "intensity": b.intensity,
                    "instructions": b.instructions,
                }
                for b in blocks
            ] if blocks else [],
        }
    
    def _get_fallback_template(self) -> Optional[Dict[str, Any]]:
        """Get generic fallback template when no specific template matches."""
        query = text("""
            SELECT 
                tt.id,
                tt.code,
                tt.name,
                tt.description,
                tt.duration_minutes,
                tt.sport,
                tt.level
            FROM train.test_template tt
            WHERE tt.sport = 'generic'
              AND tt.is_active = TRUE
            ORDER BY tt.priority ASC
            LIMIT 1
        """)
        
        result = self.db.execute(query).first()
        
        if not result:
            return None
        
        blocks_query = text("""
            SELECT 
                block_order,
                block_type,
                duration_minutes,
                intensity,
                instructions
            FROM train.test_template_block
            WHERE template_id = :template_id
            ORDER BY block_order ASC
        """)
        
        blocks = self.db.execute(blocks_query, {"template_id": result.id}).fetchall()
        
        return {
            "id": str(result.id),
            "code": result.code,
            "name": result.name,
            "description": result.description,
            "duration_minutes": result.duration_minutes,
            "sport": result.sport,
            "level": result.level,
            "blocks": [
                {
                    "block_order": b.block_order,
                    "block_type": b.block_type,
                    "duration_minutes": b.duration_minutes,
                    "intensity": b.intensity,
                    "instructions": b.instructions,
                }
                for b in blocks
            ] if blocks else [],
        }