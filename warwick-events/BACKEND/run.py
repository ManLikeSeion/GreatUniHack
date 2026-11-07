"""Local API entry point; works regardless of the terminal directory."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "warwick-events")]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("BACKEND.main:app", host="127.0.0.1", port=8000)
