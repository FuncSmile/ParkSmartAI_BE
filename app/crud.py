from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from .models import ParkingSlot, SensorLog, Prediction, SlotStatus, IoTDevice
from .utils import generate_api_key


def get_or_create_slot(
    session: Session,
    slot_id: str,
    default_floor: str = "B1",
    zone: str | None = None,
    distance_from_entry: int = 30,
) -> ParkingSlot:
    slot = session.get(ParkingSlot, slot_id)
    if not slot:
        slot = ParkingSlot(
            slot_id=slot_id,
            floor=default_floor,
            zone=zone,
            distance_from_entry=distance_from_entry,
            current_status=SlotStatus.available.value,
            last_updated=datetime.utcnow(),
        )
        session.add(slot)
        session.flush()
    return slot


def log_sensor_update(session: Session, slot_id: str, status: int, timestamp: datetime) -> ParkingSlot:
    slot = get_or_create_slot(session, slot_id)
    slot.current_status = SlotStatus.occupied.value if status == 1 else SlotStatus.available.value
    slot.last_updated = timestamp

    log = SensorLog(slot_id=slot_id, status=status, timestamp=timestamp)
    session.add(log)
    session.flush()
    return slot


def get_recent_logs(session: Session, slot_id: str, limit: int = 200):
    stmt = (
        select(SensorLog)
        .where(SensorLog.slot_id == slot_id)
        .order_by(desc(SensorLog.timestamp))
        .limit(limit)
    )
    return list(session.scalars(stmt))


def save_prediction(
    session: Session,
    slot_id: str,
    predicted_status: str,
    confidence: float,
    valid_minutes: int,
):
    now = datetime.utcnow()
    valid_until = now + timedelta(minutes=valid_minutes)

    # upsert-like: delete previous predictions for slot
    session.query(Prediction).filter(Prediction.slot_id == slot_id).delete()
    prediction = Prediction(
        slot_id=slot_id,
        prediction_time=now,
        predicted_status=predicted_status,
        confidence=confidence,
        valid_until=valid_until,
    )
    session.add(prediction)
    session.flush()
    return prediction


def get_latest_prediction(session: Session, slot_id: str) -> Optional[Prediction]:
    stmt = (
        select(Prediction)
        .where(Prediction.slot_id == slot_id)
        .order_by(desc(Prediction.prediction_time))
        .limit(1)
    )
    return session.scalars(stmt).first()


def get_map(session: Session, floor: Optional[str] = None) -> tuple[str, List[ParkingSlot]]:
    stmt = select(ParkingSlot)
    if floor:
        stmt = stmt.where(ParkingSlot.floor == floor)
    stmt = stmt.order_by(ParkingSlot.slot_id)
    slots = list(session.scalars(stmt))
    chosen_floor = floor or (slots[0].floor if slots else "B1")
    return chosen_floor, slots


def choose_recommendation(session: Session) -> tuple[Optional[ParkingSlot], float, str]:
    # get available slots
    stmt = select(ParkingSlot).where(ParkingSlot.current_status == SlotStatus.available.value)
    slots = list(session.scalars(stmt))
    if not slots:
        return None, 0.0, "No available slots"

    best_slot = None
    best_score = -1.0
    best_prob = 0.0

    for slot in slots:
        pred = get_latest_prediction(session, slot.slot_id)
        if pred and pred.predicted_status == SlotStatus.predicted_occupied.value:
            probability_available = max(0.0, 1.0 - pred.confidence)
        else:
            # base probability inversely proportional to recent occupancy rate
            logs = get_recent_logs(session, slot.slot_id, limit=50)
            if logs:
                occupied_ratio = sum(l.status for l in logs) / len(logs)
                probability_available = max(0.1, 1.0 - occupied_ratio)
            else:
                probability_available = 0.8

        score = probability_available * 0.7 + (1.0 / (1 + slot.distance_from_entry)) * 0.3
        if score > best_score:
            best_score = score
            best_slot = slot
            best_prob = probability_available

    reason = "Highest probability & closest" if best_slot else "No slots"
    return best_slot, best_prob, reason


# ---- IoT Devices ----
def get_device_by_api_key(session: Session, api_key: str) -> Optional[IoTDevice]:
    return session.query(IoTDevice).filter(IoTDevice.api_key == api_key).first()


def create_device(
    session: Session,
    slot_id: str,
    description: str | None = None,
    api_key: str | None = None,
) -> IoTDevice:
    key = api_key or generate_api_key(slot_id)
    device = IoTDevice(slot_id=slot_id, api_key=key, is_active=True, description=description)
    session.add(device)
    session.flush()
    return device


def list_devices(session: Session) -> list[IoTDevice]:
    return list(session.query(IoTDevice).order_by(IoTDevice.id))


def set_device_active(session: Session, device_id: int, active: bool) -> Optional[IoTDevice]:
    device = session.get(IoTDevice, device_id)
    if device:
        device.is_active = active
        session.flush()
    return device


def regenerate_api_key(session: Session, device_id: int) -> Optional[IoTDevice]:
    device = session.get(IoTDevice, device_id)
    if device:
        device.api_key = generate_api_key(device.slot_id)
        session.flush()
    return device


def touch_device_last_seen(session: Session, device: IoTDevice):
    device.last_seen = datetime.utcnow()
    session.flush()


def clear_all(session: Session):
    session.query(Prediction).delete()
    session.query(SensorLog).delete()
    session.query(ParkingSlot).delete()
    session.commit()
