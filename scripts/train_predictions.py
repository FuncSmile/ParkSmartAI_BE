"""Regenerate predictions based on latest sensor logs."""

from app.database import get_session, Base, engine
from app.ai import generate_predictions
from app.config import get_settings


def run():
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    with get_session() as session:
        generate_predictions(session, valid_minutes=settings.prediction_valid_minutes)
    print("Predictions regenerated")


if __name__ == "__main__":
    run()
