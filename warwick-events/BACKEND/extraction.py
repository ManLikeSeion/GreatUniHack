"""Bridge Adam's repository-root agent to the backend's shared event contract."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# The documented server command runs inside warwick-events; agent/ is its sibling.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

# Support Adam's suggested location as well as the existing root .env.
# Existing environment variables take precedence over both files.
load_dotenv(REPOSITORY_ROOT / ".env")
load_dotenv(REPOSITORY_ROOT / "agent" / ".env")

from agent.extract import process_submission
from shared.schema import Event, ExtractionResult


class ExtractionNotConfigured(RuntimeError):
    pass


def extract_events(**kwargs) -> ExtractionResult:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ExtractionNotConfigured("ANTHROPIC_API_KEY is not configured")
    extracted = process_submission(**kwargs)
    # Adam currently returns agent.schema.Event, a separate Pydantic class.
    # Validate against the canonical model at the integration boundary.
    events = [Event.model_validate(event.model_dump()).model_copy(update={"id": None})
              for event in extracted]
    return ExtractionResult(events=events)
