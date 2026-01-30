from __future__ import annotations

from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class SlotUpdate(BaseModel):
    slot_id: str = Field(..., examples=["A-03"])
    status: int = Field(..., ge=0, le=1, examples=[1])
    timestamp: datetime


class ParkingSlotOut(BaseModel):
    slot_id: str
    floor: str
    zone: str | None = None
    distance_from_entry: int
    status: str
    last_updated: datetime

    model_config = {"from_attributes": True}


class PredictionOut(BaseModel):
    slot_id: str
    predicted_status: str
    confidence: float
    valid_until: datetime

    model_config = {"from_attributes": True}


class ParkingMapResponse(BaseModel):
    floor: str
    slots: List[ParkingSlotOut]


class RecommendationItem(BaseModel):
    slot_id: str
    distance_from_entry: int
    probability_available: float


class RecommendationResponse(BaseModel):
    recommended: RecommendationItem | None
    reason: str | None = None


class ImpactRequest(BaseModel):
    saved_minutes: float


class ImpactResponse(BaseModel):
    saved_minutes: float
    co2_saved_kg: float
