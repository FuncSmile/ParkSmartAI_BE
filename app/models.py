from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy import Column, String, Integer, DateTime, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from .database import Base


class SlotStatus(str, Enum):
    available = "available"
    occupied = "occupied"
    predicted_occupied = "predicted_occupied"


class ParkingSlot(Base):
    __tablename__ = "parking_slots"

    slot_id = Column(String, primary_key=True, index=True)
    floor = Column(String, nullable=False)
    zone = Column(String, nullable=True)
    distance_from_entry = Column(Integer, nullable=False, default=0)
    current_status = Column(String, nullable=False, default=SlotStatus.available.value)
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)

    logs = relationship("SensorLog", back_populates="slot", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="slot", cascade="all, delete-orphan")


class SensorLog(Base):
    __tablename__ = "sensor_logs"

    id = Column(Integer, primary_key=True, index=True)
    slot_id = Column(String, ForeignKey("parking_slots.slot_id"), nullable=False)
    status = Column(Integer, nullable=False)  # 0=kosong, 1=terisi
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    slot = relationship("ParkingSlot", back_populates="logs")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    slot_id = Column(String, ForeignKey("parking_slots.slot_id"), nullable=False)
    prediction_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    predicted_status = Column(String, nullable=False, default=SlotStatus.available.value)
    confidence = Column(Float, nullable=False, default=0.5)
    valid_until = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(minutes=10))

    slot = relationship("ParkingSlot", back_populates="predictions")


class IoTDevice(Base):
    __tablename__ = "iot_devices"

    id = Column(Integer, primary_key=True, index=True)
    slot_id = Column(String, ForeignKey("parking_slots.slot_id"), nullable=False)
    api_key = Column(String, unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, nullable=True)

    slot = relationship("ParkingSlot")
