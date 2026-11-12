"""One-time, non-destructive migration for older Tiny Family test JSON data.

The old Home Assistant config entry must be removed and a new tiny_family
entry created. This module only copies local test data where the destination
does not exist. It never deletes the original files.
"""
from __future__ import annotations

from pathlib import Path
from shutil import copy2

_LEGACY_FILES = (
    ("person_timeline_places.json", "tiny_family_places.json"),
    ("person_timeline_historik.json", "tiny_family_historik.json"),
)


def migrate_local_json_once(config_dir: str | Path) -> tuple[str, ...]:
    """Copy old test archives to new names without replacing newer archives."""
    root = Path(config_dir)
    copied = []
    for legacy_name, new_name in _LEGACY_FILES:
        old = root / legacy_name
        new = root / new_name
        if not old.is_file() or new.exists():
            continue
        copy2(old, new)
        copied.append(new_name)
    return tuple(copied)
