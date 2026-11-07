"""In-memory events API. Run from warwick-events with uvicorn BACKEND.main:app."""

from uuid import uuid4

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from shared.schema import EXAMPLE, Event, ExtractionResult


def create_app() -> FastAPI:
    app = FastAPI(title="Warwick Events API")
    from BACKEND.workflow import create_workflow
    app.include_router(create_workflow(), prefix="/api")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Each application starts with its own validated sample and temporary store.
    samples = ExtractionResult.model_validate(EXAMPLE).events
    events = {
        f"sample-{index}": event.model_copy(update={"id": f"sample-{index}"})
        for index, event in enumerate(samples, start=1)
    }

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/events", response_model=list[Event])
    def list_events() -> list[Event]:
        return list(events.values())

    @app.get("/events/{event_id}", response_model=Event)
    def get_event(event_id: str) -> Event:
        if event_id not in events:
            raise HTTPException(status_code=404, detail="Event not found")
        return events[event_id]

    @app.post("/events", response_model=Event, status_code=status.HTTP_201_CREATED)
    def create_event(event: Event) -> Event:
        # IDs belong to the backend: never let a supplied ID overwrite an event.
        event_id = str(uuid4())
        created = event.model_copy(update={"id": event_id})
        events[event_id] = created
        return created

    return app


app = create_app()
