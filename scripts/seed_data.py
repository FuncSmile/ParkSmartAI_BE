"""Seed dummy parking data for demo."""

from datetime import datetime, timedelta

from app.database import Base, engine, get_session
from app import crud
from app.models import SlotStatus


def run():
    Base.metadata.create_all(bind=engine)
    with get_session() as session:
        crud.clear_all(session)
        now = datetime.utcnow()
        base_slots = [
            {"slot_id": "A-01", "floor": "B1", "zone": "A", "distance_from_entry": 20},
            {"slot_id": "A-02", "floor": "B1", "zone": "A", "distance_from_entry": 25},
            {"slot_id": "A-03", "floor": "B1", "zone": "A", "distance_from_entry": 30},
            {"slot_id": "A-04", "floor": "B1", "zone": "A", "distance_from_entry": 35},
            {"slot_id": "A-05", "floor": "B1", "zone": "A", "distance_from_entry": 40},
        ]

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

        for i, slot in enumerate(base_slots):
            for j in range(50):
                timestamp = now - timedelta(minutes=300 - j * 6)
                status = 1 if (i + j) % 4 == 0 else 0
                crud.log_sensor_update(session, slot["slot_id"], status=status, timestamp=timestamp)
        session.commit()

        print("Seeded", len(base_slots), "slots and logs")


if __name__ == "__main__":
    run()
