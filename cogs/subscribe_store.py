from datetime import datetime, timezone
from pathlib import Path

from loguru import logger as l
from pydantic import BaseModel
from yaml import safe_load, safe_dump

import utils as u


class SubscribeEntry(BaseModel):
    guild_id: int
    channel_id: int
    webhook_url: str
    webhook_id: int | None = None
    subscribed_by: int
    subscribed_at: datetime


class SubscribeStore:
    def __init__(self, path: str = "subscribe.yaml"):
        self._path = u.get_path(path)
        self.subscriptions: list[SubscribeEntry] = []
        self._load()

    def _load(self):
        if Path(self._path).exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = safe_load(f) or {}
                self.subscriptions = [
                    SubscribeEntry.model_validate(item)
                    for item in data.get("subscriptions", [])
                ]
                l.debug(f"[announce] Loaded {len(self.subscriptions)} subscriptions")
            except Exception as e:
                l.warning(f"[announce] Failed to load subscriptions: {e}")
                self.subscriptions = []

    def _save(self):
        try:
            data = {
                "subscriptions": [s.model_dump(mode="json") for s in self.subscriptions]
            }
            with open(self._path, "w", encoding="utf-8") as f:
                safe_dump(data, f, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            raise RuntimeError(f"Cannot write to {self._path}: {e}")

    def add(
        self,
        guild_id: int,
        channel_id: int,
        webhook_url: str,
        webhook_id: int | None,
        user_id: int,
    ) -> SubscribeEntry:
        self.remove(guild_id)
        entry = SubscribeEntry(
            guild_id=guild_id,
            channel_id=channel_id,
            webhook_url=webhook_url,
            webhook_id=webhook_id,
            subscribed_by=user_id,
            subscribed_at=datetime.now(timezone.utc),
        )
        self.subscriptions.append(entry)
        self._save()
        return entry

    def remove(self, guild_id: int) -> SubscribeEntry | None:
        removed = None
        new_list = []
        for s in self.subscriptions:
            if s.guild_id == guild_id:
                removed = s
            else:
                new_list.append(s)
        if removed:
            self.subscriptions = new_list
            self._save()
        return removed

    def get(self, guild_id: int) -> SubscribeEntry | None:
        for s in self.subscriptions:
            if s.guild_id == guild_id:
                return s
        return None

    def get_all(self) -> list[SubscribeEntry]:
        return list(self.subscriptions)

    def __len__(self) -> int:
        return len(self.subscriptions)
