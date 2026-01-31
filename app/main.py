from __future__ import annotations

from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, engine, get_session
from .models import SlotStatus, ParkingSlot, Prediction
from . import crud
from .schemas import (
    SlotUpdate,
    ParkingMapResponse,
    ParkingSlotOut,
    RecommendationResponse,
    RecommendationItem,
    ImpactRequest,
    ImpactResponse,
    PredictionOut,
)
from .websocket_manager import ConnectionManager
from .ai import generate_predictions

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
manager = ConnectionManager(max_queue=settings.websocket_broadcast_queue)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    with get_session() as session:
        yield session


@app.get("/")
def root():
    return {"status": "ok", "service": settings.app_name}


@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)
    await manager.start()
    # ensure dummy data exists
    with get_session() as session:
        if not session.query(ParkingSlot).first():
            seed_demo(session)
            session.commit()
        generate_predictions(session, valid_minutes=settings.prediction_valid_minutes)


@app.post("/api/iot/slot-update")
async def update_slot(payload: SlotUpdate, db: Session = Depends(get_db)):
    slot = crud.log_sensor_update(db, payload.slot_id, payload.status, payload.timestamp)
    db.commit()
    # refresh predictions for this slot context
    generate_predictions(db, valid_minutes=settings.prediction_valid_minutes)

    response_payload = {
        "event": "slot_update",
        "slot_id": slot.slot_id,
        "status": slot.current_status,
        "timestamp": payload.timestamp.isoformat(),
    }
    await manager.send_json(response_payload)
    return {"message": "updated", "slot": slot.slot_id}


@app.get("/api/parking/map", response_model=ParkingMapResponse)
def get_parking_map(
    location: str | None = Query(default=None, description="Optional location code"),
    floor: str | None = Query(default=None, description="Floor identifier e.g. B1"),
    db: Session = Depends(get_db),
):
    selected_floor, slots = crud.get_map(db, floor=floor)
    enriched_slots: list[ParkingSlotOut] = []
    for slot in slots:
        prediction = crud.get_latest_prediction(db, slot.slot_id)
        status = slot.current_status
        if prediction and prediction.predicted_status == SlotStatus.predicted_occupied.value and status == SlotStatus.available.value:
            status = SlotStatus.predicted_occupied.value
        enriched_slots.append(
            ParkingSlotOut(
                slot_id=slot.slot_id,
                floor=slot.floor,
                zone=slot.zone,
                distance_from_entry=slot.distance_from_entry,
                status=status,
                last_updated=slot.last_updated,
            )
        )
    return ParkingMapResponse(floor=selected_floor, slots=enriched_slots)


@app.get("/api/parking/recommendation", response_model=RecommendationResponse)
def recommend_slot(db: Session = Depends(get_db)):
    slot, probability, reason = crud.choose_recommendation(db)
    if not slot:
        return RecommendationResponse(recommended=None, reason=reason)
    item = RecommendationItem(
        slot_id=slot.slot_id,
        distance_from_entry=slot.distance_from_entry,
        probability_available=round(probability, 3),
    )
    return RecommendationResponse(recommended=item, reason=reason)


@app.get("/api/parking/predictions", response_model=list[PredictionOut])
def list_predictions(db: Session = Depends(get_db)):
    predictions = db.query(Prediction).all()
    return [
        PredictionOut(
            slot_id=p.slot_id,
            predicted_status=p.predicted_status,
            confidence=p.confidence,
            valid_until=p.valid_until,
        )
        for p in predictions
    ]


@app.post("/api/impact", response_model=ImpactResponse)
def calculate_impact(body: ImpactRequest):
    co2_saved = round(body.saved_minutes * 0.08, 3)
    return ImpactResponse(saved_minutes=body.saved_minutes, co2_saved_kg=co2_saved)


@app.websocket("/ws/slots")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive; clients can ignore
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ---- Demo seed helpers ----

def seed_demo(session: Session):
    base_slots = [
        {"slot_id": "A-01", "floor": "B1", "zone": "A", "distance_from_entry": 20},
        {"slot_id": "A-02", "floor": "B1", "zone": "A", "distance_from_entry": 25},
        {"slot_id": "A-03", "floor": "B1", "zone": "A", "distance_from_entry": 30},
        {"slot_id": "A-04", "floor": "B1", "zone": "A", "distance_from_entry": 35},
        {"slot_id": "A-05", "floor": "B1", "zone": "A", "distance_from_entry": 40},
    ]
    now = datetime.utcnow()
    for slot in base_slots:
        obj = crud.get_or_create_slot(
            session,
            slot_id=slot["slot_id"],
            default_floor=slot["floor"],
            zone=slot.get("zone"),
            distance_from_entry=slot["distance_from_entry"],
        )
        obj.current_status = SlotStatus.available.value
        obj.last_updated = now
    session.commit()

    # seed logs for each slot to allow predictions
    for i, slot in enumerate(base_slots):
        for j in range(10):
            timestamp = now - timedelta(minutes=60 - j * 6)
            status = 1 if (i + j) % 3 == 0 else 0
            crud.log_sensor_update(session, slot["slot_id"], status=status, timestamp=timestamp)
    session.commit()
