"""Config flow for WaterFurnace integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from waterfurnace.waterfurnace import (
    WaterFurnace,
    WFCredentialError,
    WFError,
    WFException,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_LOCATION, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class WaterFurnaceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WaterFurnace."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str | None = None
        self._password: str | None = None
        self._discovered_devices: list[dict[str, Any]] = []

    async def _discover_devices_and_locations(
        self, username: str, password: str
    ) -> list[dict[str, Any]]:
        """Discover available devices and locations from WaterFurnace API.

        Returns list of dicts with keys:
        - device_index: int
        - location_index: int
        - gwid: str
        """
        discovered = []

        # Try locations 0-9 (reasonable limit)
        for location_idx in range(10):
            location_has_devices = False

            # Try devices 0-9 at this location
            for device_idx in range(10):
                client = WaterFurnace(
                    username, password, device=device_idx, location=location_idx
                )
                try:
                    await self.hass.async_add_executor_job(client.login)
                    if client.gwid:
                        discovered.append(
                            {
                                "device_index": device_idx,
                                "location_index": location_idx,
                                "gwid": client.gwid,
                            }
                        )
                        location_has_devices = True
                except WFError:
                    # Device index out of range, stop trying devices at this location
                    break
                except (WFCredentialError, WFException):
                    # Other errors should propagate
                    raise

            # If no devices found at this location, stop trying locations
            if not location_has_devices and location_idx > 0:
                break

        return discovered

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            client = WaterFurnace(username, password)

            try:
                # Login is a blocking call, run in executor
                await self.hass.async_add_executor_job(client.login)
            except WFCredentialError:
                errors["base"] = "invalid_auth"
            except WFException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error connecting to WaterFurnace")
                errors["base"] = "unknown"

            if not errors:
                # Store credentials for next step
                self._username = username
                self._password = password

                # Discover available devices
                try:
                    discovered = await self._discover_devices_and_locations(
                        username, password
                    )
                except WFCredentialError:
                    errors["base"] = "invalid_auth"
                except WFException:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error discovering devices")
                    errors["base"] = "unknown"

                if not errors:
                    if not discovered:
                        errors["base"] = "no_devices_found"
                    else:
                        self._discovered_devices = discovered
                        # If only one device, auto-create entry
                        if len(discovered) == 1:
                            return await self.async_step_select_device()
                        # Multiple devices, show selection step
                        return await self.async_step_select_device()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device selection from discovered devices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_index = int(user_input.get("device_selection", 0))
            if selected_index >= len(self._discovered_devices):
                errors["base"] = "invalid_selection"
            else:
                selected_device = self._discovered_devices[selected_index]
                gwid = selected_device["gwid"]
                device = selected_device["device_index"]
                location = selected_device["location_index"]

                # Check if this device is already configured
                await self.async_set_unique_id(gwid)
                self._abort_if_unique_id_configured()

                data = {
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_DEVICE: device,
                    CONF_LOCATION: location,
                }

                title = f"WaterFurnace {self._username}"
                if device != 0 or location != 0:
                    title = f"{title} (Device {device}, Location {location})"

                return self.async_create_entry(title=title, data=data)

        # Build device selection options, filtering out already configured devices
        options = []
        configured_gwids = {
            entry.unique_id for entry in self.hass.config_entries.async_entries(DOMAIN)
        }

        available_devices = []
        for idx, device_info in enumerate(self._discovered_devices):
            gwid = device_info["gwid"]
            device_idx = device_info["device_index"]
            location_idx = device_info["location_index"]

            # Skip already configured devices
            if gwid in configured_gwids:
                continue

            available_devices.append((idx, device_info))
            label = f"Location {location_idx} - Device {device_idx} ({gwid})"
            options.append(SelectOptionDict(value=str(idx), label=label))

        if not options:
            errors["base"] = "no_devices_found"
            return self.async_show_form(
                step_id="select_device",
                errors=errors,
            )

        # If only one device available, auto-select it
        if len(available_devices) == 1:
            idx, selected_device = available_devices[0]
            gwid = selected_device["gwid"]
            device = selected_device["device_index"]
            location = selected_device["location_index"]

            await self.async_set_unique_id(gwid)
            self._abort_if_unique_id_configured()

            data = {
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_DEVICE: device,
                CONF_LOCATION: location,
            }

            title = f"WaterFurnace {self._username}"
            if device != 0 or location != 0:
                title = f"{title} (Device {device}, Location {location})"

            return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device_selection"): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        username = import_data[CONF_USERNAME]
        password = import_data[CONF_PASSWORD]

        client = WaterFurnace(username, password)

        try:
            # Login is a blocking call, run in executor
            await self.hass.async_add_executor_job(client.login)
        except WFCredentialError:
            return self.async_abort(reason="invalid_auth")
        except WFException:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected error importing WaterFurnace configuration")
            return self.async_abort(reason="unknown")

        gwid = client.gwid
        if not gwid:
            # This likely indicates a server-side change, or an implementation bug
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(gwid)
        self._abort_if_unique_id_configured()

        data = {**import_data}
        # Ensure data has device and location fields
        data[CONF_DEVICE] = 0
        data[CONF_LOCATION] = 0

        title = f"WaterFurnace {username}"

        return self.async_create_entry(
            title=title,
            data=data,
        )
