from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from app.services.stress_analysis import snapshot, simulate

router = APIRouter(prefix='/api/stress', tags=['stress'])
class StressRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    mode: Literal['observed','assumed'] = 'observed'
    price: float = Field(210000, gt=0, le=10000000)
    index: float = Field(5500, gt=0, le=100000)
    beta: float = Field(1.2, ge=-5, le=5)
    target_index: float = Field(5500, gt=0, le=100000)
    residual_pct: float = Field(2, gt=0, le=30)
    days: int = Field(5, ge=1, le=60)
    foreign_sell: float = Field(0, ge=0, le=1000000)
    turnover: float = Field(10000, gt=0, le=1000000)
    impact_pct: float = Field(1, ge=0, le=20)

@router.get('/snapshot')
def get_snapshot():
    return snapshot()

@router.post('/simulate')
def run_simulation(payload: StressRequest):
    try:
        return simulate(payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
