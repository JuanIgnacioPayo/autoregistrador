import os
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional
from playwright.sync_api import sync_playwright, BrowserContext, Playwright

from user_forge.config.settings import settings

logger = logging.getLogger(__name__)

class BrowserManager:
    """
    Manages isolated persistent browser profiles per account.
    Profiles are stored in: ./browser_profiles/<project>/<username>/
    Ensuring cookies, local storage, cache, and canvas fingerprints remain completely isolated.
    """
    def __init__(self, base_profiles_dir: Optional[Path] = None):
        self.base_profiles_dir = base_profiles_dir or settings.PROFILES_DIR
        self._playwright: Optional[Playwright] = None

    def get_profile_path(self, project_id: str, username: str) -> Path:
        safe_proj = "".join(c for c in project_id if c.isalnum() or c in ("-", "_")).lower()
        safe_user = "".join(c for c in username if c.isalnum() or c in ("-", "_", ".")).lower()
        profile_path = self.base_profiles_dir / safe_proj / safe_user
        profile_path.mkdir(parents=True, exist_ok=True)
        return profile_path

    def clean_stale_locks(self, profile_dir: Path):
        """
        Cleans orphaned processes and Chromium singleton lock files.
        If a previous browser window was closed abruptly or left background child processes,
        this ensures Chromium can launch cleanly without hanging or error code 32.
        """
        # 1. Terminate any orphaned ms-playwright chrome processes on Windows
        try:
            ps_script = "Get-Process -Name chrome -ErrorAction SilentlyContinue | Select-Object Id, Path | ConvertTo-Json"
            raw = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps_script],
                timeout=4
            ).decode("utf-8", errors="ignore").strip()
            if raw:
                items = json.loads(raw)
                if isinstance(items, dict):
                    items = [items]
                pids_to_kill = [i["Id"] for i in items if "ms-playwright" in (i.get("Path") or "").lower()]
                for pid in pids_to_kill:
                    try:
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Process cleanup note: {e}")

        # 2. Delete singleton lock files
        for lock_name in ["lockfile", "SingletonLock", "SingletonSocket", "SingletonCookie"]:
            lf = profile_dir / lock_name
            if lf.exists():
                try:
                    lf.unlink()
                except Exception:
                    pass

    def launch_persistent_context(
        self,
        project_id: str,
        username: str,
        headless: bool = False,
        channel: Optional[str] = "chrome",
        viewport_width: int = 1280,
        viewport_height: int = 800
    ) -> tuple[Playwright, BrowserContext]:
        profile_dir = self.get_profile_path(project_id, username)
        self.clean_stale_locks(profile_dir)
        
        playwright = sync_playwright().start()
        
        launch_kwargs = {
            "user_data_dir": str(profile_dir),
            "headless": headless,
            "viewport": None,  # Allows native window sizing
            "locale": "es-AR",
            "timezone_id": "America/Argentina/Buenos_Aires",
            "ignore_https_errors": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--start-maximized",
                "--ignore-certificate-errors",
                "--ignore-ssl-errors"
            ]
        }

        # Select browser channel: 'chrome' (Google Chrome) or 'msedge' (Microsoft Edge) or default bundled Chromium
        target_channel = (channel or "chrome").strip().lower()
        if target_channel in ("chrome", "msedge"):
            launch_kwargs["channel"] = target_channel
        
        try:
            context = playwright.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as e:
            logger.warning(f"Could not launch browser with channel={target_channel}: {e}. Retrying with fallback...")
            # Fallback 1: try the other native browser or bundled Chromium
            fallback_channel = "msedge" if target_channel == "chrome" else None
            if fallback_channel:
                launch_kwargs["channel"] = fallback_channel
            else:
                launch_kwargs.pop("channel", None)
            try:
                context = playwright.chromium.launch_persistent_context(**launch_kwargs)
            except Exception:
                launch_kwargs.pop("channel", None)
                context = playwright.chromium.launch_persistent_context(**launch_kwargs)

        return playwright, context
