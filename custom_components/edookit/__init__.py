"""Edookit (Czech school information system) integration for Home Assistant."""

from __future__ import annotations

from datetime import date
import json
import logging
from pathlib import Path
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .api import EdookitAuthError, EdookitClient, EdookitError
from .central import SchoolCoordinator
from .const import (
    CONF_API_PASSWORD,
    CONF_API_USERNAME,
    CONF_LOGIN_METHOD,
    CONF_OIDC_CLIENT_ID,
    CONF_SCHOOL,
    DOMAIN,
    LOGIN_AUTO,
    SERVICE_DUMP_PAGES,
    SERVICE_GET_TIMETABLE,
    SERVICE_REFRESH,
    STORAGE_VERSION,
)
from .coordinator import (
    PAGES,
    ChildRuntime,
    EdookitConfigEntry,
    EdookitDataCoordinator,
    EdookitRuntimeData,
    TimetableCoordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CALENDAR, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ATTR_ENTRY_ID = "config_entry_id"
ATTR_WHAT = "what"
ATTR_START = "start_date"
ATTR_END = "end_date"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services."""
    _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EdookitConfigEntry) -> bool:
    """Set up Edookit from a config entry."""
    session = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar())
    client = EdookitClient(
        session,
        entry.data[CONF_SCHOOL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data.get(CONF_LOGIN_METHOD, LOGIN_AUTO),
        oidc_client_id=entry.options.get(CONF_OIDC_CLIENT_ID) or entry.data.get(CONF_OIDC_CLIENT_ID),
        api_username=entry.options.get(CONF_API_USERNAME),
        api_password=entry.options.get(CONF_API_PASSWORD),
    )
    store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}", private=True)
    stored: dict[str, Any] = await store.async_load() or {}
    client.import_cookies(stored.get("cookies"))

    # A parent account can see several children (switcher at the top of the portal).
    try:
        found = await client.async_get_children()
    except EdookitAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except EdookitError as err:
        raise ConfigEntryNotReady(str(err)) from err

    children: list[ChildRuntime] = []
    for child in found:
        data = EdookitDataCoordinator(hass, entry, client, store, stored, child)
        timetable = TimetableCoordinator(hass, entry, client, store, stored, child)
        children.append(ChildRuntime(child, timetable, data))

    entry.runtime_data = EdookitRuntimeData(client, store, stored, children)
    # Portal discovery failures must not delete existing child devices or their history.

    central = SchoolCoordinator(hass, entry, entry.runtime_data)
    entry.runtime_data.central = central
    await central.async_config_entry_first_refresh()
    # A listener activates the account timer; data views never poll themselves.
    entry.async_on_unload(central.async_add_listener(lambda: None))
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: EdookitConfigEntry) -> bool:
    """Unload a config entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.central.async_shutdown()
        await entry.runtime_data.store.async_save(entry.runtime_data.stored)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete stored cookies when the entry is removed."""
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()


# ------------------------------------------------------------------ services


def _entries(hass: HomeAssistant, call: ServiceCall) -> list[EdookitConfigEntry]:
    entry_id = call.data.get(ATTR_ENTRY_ID)
    entries = [
        e for e in hass.config_entries.async_loaded_entries(DOMAIN) if entry_id is None or e.entry_id == entry_id
    ]
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_not_found")
    return entries


def _register_services(hass: HomeAssistant) -> None:
    async def school_action(call: ServiceCall) -> ServiceResponse:
        entry = next(iter(_entries(hass, call)))
        if not entry.options.get("allow_school_actions", False):
            raise ServiceValidationError("School actions are disabled")
        student_id = call.data["student_id"]
        child = next((child for child in entry.runtime_data.children if child.child.key == student_id), None)
        if child is None:
            raise ServiceValidationError("Unknown student")
        action = call.data["action"]
        key = "homework" if action == "complete_homework" else "messages"
        payload = (entry.runtime_data.central.data or {}).get(student_id, {})
        item = next((item for item in payload.get(key, []) if item.get("id") == call.data["item_id"]), None)
        if item is None or not item.get("url"):
            raise ServiceValidationError("Item is not in the verified school data")
        try:
            async with entry.runtime_data.client.as_child(child.child):
                if action == "complete_homework":
                    result = {"changed": await entry.runtime_data.client.async_complete_assignment(item["url"])}
                else:
                    result = {"detail": await entry.runtime_data.client.async_read_message(item["url"])}
            await entry.runtime_data.central.async_manual_refresh()
        except EdookitError as err:
            raise ServiceValidationError("School action could not be confirmed") from err
        return {"ok": True, **result}

    async def refresh(call: ServiceCall) -> None:
        for entry in _entries(hass, call):
            await entry.runtime_data.central.async_manual_refresh()

    async def dump_pages(call: ServiceCall) -> ServiceResponse:
        folder = Path(hass.config.path("edookit_debug"))
        written: list[str] = []

        def _write(target: Path, text: str) -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

        for entry in _entries(hass, call):
            client = entry.runtime_data.client
            base = folder / client.school
            children = [rt.child for rt in entry.runtime_data.children]
            await hass.async_add_executor_job(
                _write,
                base / "children.json",
                json.dumps([c.__dict__ for c in children], ensure_ascii=False, indent=2),
            )
            for rt in entry.runtime_data.children:
                child = rt.child
                pages = {**PAGES, "timetable": "/timetable/"}
                async with client.as_child(child):
                    for key, path in pages.items():
                        try:
                            html = await client.async_get_page(path)
                        except Exception as err:
                            html = f"<!-- error: {err} -->"
                        target = base / (child.key or "default") / f"{key}.html"
                        await hass.async_add_executor_job(_write, target, html)
                        written.append(str(target))
        _LOGGER.warning(
            "Edookit pages saved to %s. They contain personal data - anonymise them before sharing",
            folder,
        )
        return {"files": written}

    async def get_timetable(call: ServiceCall) -> ServiceResponse:
        start: date = call.data.get(ATTR_START) or dt_util.now().date()
        end: date = call.data.get(ATTR_END) or start
        result = {}
        for entry in _entries(hass, call):
            result[entry.entry_id] = [
                {
                    "student": child.name,
                    "child_id": child.child.id,
                    "lessons": [
                        ls
                        for ls in (child.timetable.data or {}).get("lessons", [])
                        if start.isoformat() <= ls["date"] <= end.isoformat()
                    ],
                }
                for child in entry.runtime_data.children
            ]
        return result

    entry_schema = {vol.Optional(ATTR_ENTRY_ID): cv.string}
    hass.services.async_register(
        DOMAIN,
        "school_action",
        school_action,
        schema=vol.Schema(
            {
                vol.Required(ATTR_ENTRY_ID): cv.string,
                vol.Optional("student_id", default=""): cv.string,
                vol.Required("item_id"): cv.string,
                vol.Required("action"): vol.In(["complete_homework", "read_message"]),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        refresh,
        schema=vol.Schema(
            {**entry_schema, vol.Optional(ATTR_WHAT, default="all"): vol.In(["all", "timetable", "data"])}
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DUMP_PAGES,
        dump_pages,
        schema=vol.Schema(entry_schema),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TIMETABLE,
        get_timetable,
        schema=vol.Schema({**entry_schema, vol.Optional(ATTR_START): cv.date, vol.Optional(ATTR_END): cv.date}),
        supports_response=SupportsResponse.ONLY,
    )
