"""One polling coordinator per account; legacy entity coordinators are data views."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import timedelta
import json
import logging

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .coordinator import _save
from .school import poll_delay, school_payload

_LOGGER = logging.getLogger(__name__)


class SchoolCoordinator(DataUpdateCoordinator):
    """Serialize requests, persist the last result and publish only the chosen child."""

    def __init__(self, hass, entry, runtime):
        super().__init__(
            hass, _LOGGER, config_entry=entry, name="Edookit account", update_interval=timedelta(minutes=45)
        )
        self.runtime = runtime
        self._manual = False
        self._refresh_lock = asyncio.Lock()
        cached = runtime.stored.get("last_success", {})
        for child in runtime.children:
            old = cached.get(child.child.key, {})
            for key, view in (("data", child.data), ("timetable", child.timetable)):
                view.update_interval = None
                view.central = self
                if old.get(key):
                    view.async_set_updated_data(deepcopy(old[key]))

    async def async_manual_refresh(self):
        self._manual = True
        self.runtime.client.invalidate_timetable_cache()
        try:
            await self.async_refresh()
        finally:
            self._manual = False

    async def _async_update_data(self):
        async with self._refresh_lock:
            return await self._fetch_account()

    async def _fetch_account(self):
        now = dt_util.now()
        quiet = now.hour >= 22 or now.hour < 6
        result = {}
        auth_error = None
        for child in self.runtime.children:
            for view in (child.data, child.timetable):
                if quiet and not self._manual and view.data:
                    continue
                try:
                    fetched = await view._async_update_data()
                    if view is child.data and len(self.runtime.children) > 1 and not child.child.url:
                        # Family pages cannot safely assign unscoped lists to each child.
                        for field in ("assignments", "exams"):
                            fetched[field] = []
                            fetched["section_status"][field] = "unverified_student"
                    view.async_set_updated_data(fetched)
                except ConfigEntryAuthFailed as err:
                    auth_error = err
                    stale = deepcopy(view.data or {})
                    stale["sync_status"] = "auth_error"
                    if view is child.data:
                        stale["section_status"] = {key: "auth_error" for key in ("assignments", "exams")}
                    view.async_set_updated_data(stale)
                except (UpdateFailed, ValueError, KeyError, TypeError):
                    stale = deepcopy(view.data or {})
                    stale["sync_status"] = "stale" if stale.get("updated") else "error"
                    if view is child.data:
                        stale["section_status"] = {
                            key: "stale" if key in stale else "error" for key in ("assignments", "exams")
                        }
                    view.async_set_updated_data(stale)
            result[child.child.key] = school_payload(
                child.child.key,
                child.timetable.data or {},
                child.data.data or {},
                self.runtime.client.base_url,
                now,
                entry_id=self.config_entry.entry_id,
                allow_actions=self.config_entry.options.get("allow_school_actions", False),
            )

        school_day = any(
            ls.get("date") == now.date().isoformat()
            and not ls.get("cancelled")
            and ls.get("kind", "lesson") == "lesson"
            for child in self.runtime.children
            for ls in (child.timetable.data or {}).get("lessons", [])
        )
        self.update_interval = poll_delay(now, school_day)
        self.runtime.stored["last_success"] = {
            child.child.key: {"data": child.data.data, "timetable": child.timetable.data}
            for child in self.runtime.children
        }
        await _save(self.runtime.store, self.runtime.stored, self.runtime.client)

        topic = self.config_entry.options.get("school_mqtt_topic", "")
        selected = self.config_entry.options.get("school_student_id", "")
        if (
            topic
            and topic.endswith("/school/set")
            and not any(char in topic for char in ("+", "#", "\0"))
            and selected in result
        ):
            from homeassistant.components import mqtt

            try:
                await mqtt.async_publish(
                    self.hass, topic, json.dumps(result[selected], ensure_ascii=False), qos=1, retain=True
                )
            except Exception:
                _LOGGER.warning("School MQTT publish failed; retained portal data remains available")
        if auth_error:
            raise auth_error
        return result
