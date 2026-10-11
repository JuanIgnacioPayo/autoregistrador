import json
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.sync_api import BrowserContext

from user_forge.core.models import SessionState

class SessionSaver:
    """
    Exports and inspects Playwright storage states (cookies, localStorage)
    to persistent JSON files inside the account profile directory.
    """
    @staticmethod
    def save_session_state(context: BrowserContext, target_dir: Path) -> SessionState:
        target_dir.mkdir(parents=True, exist_ok=True)
        state_file = target_dir / "storage_state.json"
        
        context.storage_state(path=str(state_file))

        cookies_count = len(context.cookies())
        return SessionState(
            account_id=0,
            storage_state_path=str(state_file),
            cookies_count=cookies_count
        )

    @staticmethod
    def get_state_summary(target_dir: Path) -> Dict[str, Any]:
        state_file = target_dir / "storage_state.json"
        if not state_file.exists():
            return {"exists": False, "cookies": 0, "origins": 0}
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "exists": True,
                "cookies": len(data.get("cookies", [])),
                "origins": len(data.get("origins", []))
            }
        except Exception:
            return {"exists": False, "cookies": 0, "origins": 0}
