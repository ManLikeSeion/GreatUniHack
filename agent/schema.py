"""Shared event contract for the whole team.

Person 1 (agent) produces Event objects, Person 2 (API/DB) stores them,
Person 3 (frontend) renders them. Change this file only after telling the others.

Datetimes are ISO 8601 strings in Europe/London, e.g. "2026-11-13T19:00:00+00:00".
Unknown values are null, never guessed: set needs_review instead.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal[
    "sports", "cultural", "academic", "social",
    "careers", "arts", "charity", "other",
]
Source = Literal["text", "poster", "scrape", "calendar", "manual"]


class Event(BaseModel):
    id: Optional[str] = Field(None, description="Assigned by the backend, not the agent")
    title: str
    society: str = Field(description="Society name as it appears in the input")
    society_id: Optional[str] = Field(None, description="Canonical ID, filled by the backend")
    category: Category
    start: Optional[datetime] = Field(None, description="Null if date/time not stated")
    end: Optional[datetime] = None
    location: Optional[str] = None
    description: Optional[str] = Field(None, description="One or two sentences max")
    source: Source = "text"
    confidence: float = Field(ge=0, le=1, description="Overall extraction confidence")
    needs_review: bool = Field(description="True if date, time or location is missing/ambiguous")
    review_reasons: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """One caption or poster can contain several events."""
    events: list[Event]


# JSON schema to pass as the input_schema of the Claude tool that forces structured output.
TOOL_SCHEMA = ExtractionResult.model_json_schema()

EXAMPLE = {
    "events": [
        {
            "title": "Beginners Muay Thai Session",
            "society": "Warwick Thai Boxing",
            "category": "sports",
            "start": "2026-11-13T19:00:00+00:00",
            "end": "2026-11-13T20:30:00+00:00",
            "location": "Sports Hub",
            "description": "Open session for complete beginners, no kit needed.",
            "source": "text",
            "confidence": 0.93,
            "needs_review": False,
            "review_reasons": [],
        }
    ]
}

if __name__ == "__main__":
    # Sanity check: the example must validate against the model.
    print(ExtractionResult.model_validate(EXAMPLE).events[0].title)
