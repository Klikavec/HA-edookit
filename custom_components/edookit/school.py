"""Versioned school data contract, independent of Home Assistant."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
from typing import Any
from urllib.parse import urljoin, urlsplit

SCHEMA_VERSION = 1


def stable_items(items: list[dict], kind: str, student: str) -> list[dict]:
    """Prefer portal IDs/URLs; fallback identity deliberately excludes mutable text."""
    result = {}
    for item in items:
        identity = (
            item.get("id")
            or item.get("url")
            or json.dumps(
                [item.get("subject"), item.get("title"), item.get("due") or item.get("date")],
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        key = hashlib.sha256(f"{student}|{kind}|{identity}".encode()).hexdigest()[:24]
        result[key] = {**item, "id": key}
    return list(result.values())


def safe_url(value: str | None, base: str) -> str | None:
    """Only portal links are eligible to be opened from the panel."""
    if not value:
        return None
    url = urljoin(base, value)
    parsed = urlsplit(url)
    return url if parsed.scheme == "https" and parsed.netloc == urlsplit(base).netloc else None


def school_payload(
    student_id: str,
    timetable: dict,
    data: dict,
    base: str,
    now: datetime,
    *,
    entry_id: str = "",
    allow_actions: bool = False,
) -> dict[str, Any]:
    """Never project lessons into an unavailable week or claim unknown lists empty."""
    sections = data.get("section_status", {})
    homework = stable_items(data.get("assignments", []), "homework", student_id)
    exams = stable_items(data.get("exams", []), "exam", student_id)
    messages = stable_items(data.get("messages", [])[:30], "message", student_id)
    for item in homework + exams + messages:
        item["url"] = safe_url(item.get("url"), base)
    start = now.date() - timedelta(days=now.weekday())
    available = sorted({ls["date"] for ls in timetable.get("lessons", [])})
    weeks = [
        {
            "start": (start + timedelta(days=7 * i)).isoformat(),
            "status": "available"
            if any(
                (start + timedelta(days=7 * i)).isoformat() <= d < (start + timedelta(days=7 * (i + 1))).isoformat()
                for d in available
            )
            else "unavailable",
        }
        for i in range(2)
    ]
    statuses = {
        "messages": sections.get("inbox", "unknown"),
        "timetable": timetable.get("sync_status", "unknown"),
        "homework": sections.get("assignments", "unknown"),
        "exams": sections.get("exams", "unknown"),
    }
    timestamps = data.get("section_updated", {})
    success = [timetable.get("updated"), timestamps.get("assignments"), timestamps.get("exams")]
    return {
        "schema_version": SCHEMA_VERSION,
        "student_id": student_id,
        "entry_id": entry_id,
        "actions_enabled": allow_actions,
        "timezone": "Europe/Prague",
        "timetable": {"days": timetable.get("days", []), "bell": timetable.get("bell", []), "weeks": weeks},
        "homework": homework,
        "exams": exams,
        "messages": messages,
        "last_updated": min(success) if all(success) else None,
        "published_at": now.isoformat(),
        "sync_status": "ok" if all(s == "ok" for s in statuses.values()) else "stale" if any(success) else "error",
        "sections": statuses,
    }


def poll_delay(now: datetime, school_day: bool) -> timedelta:
    """Use wall clock in Europe/Prague; no automatic portal traffic 22:00–06:00."""
    if now.hour >= 22 or now.hour < 6:
        morning = now.replace(hour=6, minute=0, second=0, microsecond=0)
        if now.hour >= 22:
            morning += timedelta(days=1)
        # UTC subtraction handles DST transitions inside the quiet period.
        from datetime import UTC

        return morning.astimezone(UTC) - now.astimezone(UTC)
    return timedelta(minutes=45 if school_day and 6 <= now.hour < 16 else 180)
