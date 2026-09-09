"""Append-only Life OS completion ledger, independent of the legacy XP store."""
import json
import os
from pathlib import Path
from threading import Lock

_lock = Lock()


def append_event(path: Path, date: str, quest_id: str, xp: int) -> bool:
    """Atomically add one event per date/quest; never open shadow_state.json."""
    with _lock:
        events = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        if not isinstance(events, list):
            raise ValueError("Life OS ledger must be a JSON array")
        if any(e["date"] == date and e["questId"] == quest_id for e in events):
            return False
        events.append({"date": date, "questId": quest_id, "xp": xp})
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
        return True
