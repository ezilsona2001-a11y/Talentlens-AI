import json
from pathlib import Path

def load_history(path: Path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []

def save_analysis(path: Path, item: dict):
    history = load_history(path)
    history = [x for x in history if x.get("id") != item.get("id")]
    history.insert(0, item)
    history = history[:100]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return history

def delete_analysis(path: Path, item_id: str):
    history = [x for x in load_history(path) if x.get("id") != item_id]
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return history
