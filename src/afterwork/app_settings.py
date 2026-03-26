from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SETTINGS_DIR = Path.home() / ".afterwork"
SETTINGS_PATH = SETTINGS_DIR / "settings.json"
class SettingsStore:
    def __init__(self, path: Path = SETTINGS_PATH) -> None:
        self.path = path

    def ensure_exists(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps(self.default_settings(), indent=2), encoding="utf-8")

    def default_settings(self) -> dict[str, Any]:
        return {
            "last_scenario_path": None,
        }

    def load(self) -> dict[str, Any]:
        self.ensure_exists()
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, settings: dict[str, Any]) -> None:
        self.ensure_exists()
        self.path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    def set_last_scenario_path(self, scenario_path: Path | None) -> None:
        settings = self.load()
        settings["last_scenario_path"] = str(scenario_path) if scenario_path is not None else None
        self.save(settings)

    def get_last_scenario_path(self) -> Path | None:
        settings = self.load()
        raw_path = settings.get("last_scenario_path")
        if not raw_path:
            return None
        return Path(raw_path)

    def get_autosave_path(self) -> Path:
        self.ensure_exists()
        return self.path.parent / "autosave.json"
