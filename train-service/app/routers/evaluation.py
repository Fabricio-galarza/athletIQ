# app/routers/evaluation.py
"""
CU-TRAIN-01-HU-05: Automatic evaluation endpoint.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.context import RequireAthlete, UserContext
from app.infra.db.session import get_db
from app.services.sufficiency_service import SufficiencyService

router = APIRouter(prefix="/evaluate", tags=["Evaluation"])


@router.get("/sufficiency", status_code=status.HTTP_200_OK)
async def evaluate_sufficiency(
    sport_id: str,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """
    CU-TRAIN-01-HU-05:Evaluate whether the athlete has sufficient data.
    """
    service = SufficiencyService(db, context.user_id, sport_id, context)
    result = service.evaluate()
    return result