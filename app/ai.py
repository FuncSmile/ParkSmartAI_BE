from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from .models import SensorLog, SlotStatus
from .crud import get_recent_logs, save_prediction


def _compute_future_occupancy_probability(logs: List[SensorLog]) -> float:
    if not logs:
        return 0.3

    now = datetime.utcnow()
    horizon = now - timedelta(hours=2)
    recent = [l for l in logs if l.timestamp >= horizon]
    window = recent if recent else logs

    if not window:
        return 0.3

    # recency-weighted average: last 30 minutes get higher weight
    thirty_min_ago = now - timedelta(minutes=30)
    weights = []
    values = []
    for log in window:
        values.append(log.status)
        if log.timestamp >= thirty_min_ago:
            weights.append(1.5)
        else:
            weights.append(1.0)

    weighted_sum = sum(v * w for v, w in zip(values, weights))
    prob = weighted_sum / sum(weights)

    # normalize to [0.05, 0.95]
    prob = max(0.05, min(0.95, prob))
    return prob


def generate_predictions(session: Session, valid_minutes: int = 10):
    from .models import ParkingSlot  # local import to avoid circular

    slots = session.query(ParkingSlot).all()
    for slot in slots:
        logs = get_recent_logs(session, slot.slot_id, limit=200)
        probability_occupied = _compute_future_occupancy_probability(logs)

        if slot.current_status == SlotStatus.available.value:
            predicted_status = (
                SlotStatus.predicted_occupied.value if probability_occupied >= 0.6 else SlotStatus.available.value
            )
        else:
            predicted_status = SlotStatus.occupied.value

        confidence = probability_occupied if predicted_status != SlotStatus.available.value else 1 - probability_occupied
        confidence = round(confidence, 3)

        save_prediction(
            session=session,
            slot_id=slot.slot_id,
            predicted_status=predicted_status,
            confidence=confidence,
            valid_minutes=valid_minutes,
        )
    session.commit()
