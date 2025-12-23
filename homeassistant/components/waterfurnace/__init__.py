"""Support for WaterFurnace geothermal systems."""

from __future__ import annotations

import logging

import voluptuous as vol
from waterfurnace.waterfurnace import WaterFurnace, WFCredentialError, WFException

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DEVICE, DOMAIN
from .coordinator import WaterFurnaceDataUpdateCoordinator
from .models import WaterFurnaceConfigEntry, WaterFurnaceData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up WaterFurnace from yaml configuration."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config[DOMAIN],
            )
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: WaterFurnaceConfigEntry
) -> bool:
    """Set up WaterFurnace from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    device = entry.data.get(CONF_DEVICE, 0)

    client = WaterFurnace(username, password, device=device)

    try:
        await hass.async_add_executor_job(client.login)
    except WFCredentialError as err:
        _LOGGER.error("Invalid credentials for WaterFurnace device")
        raise ConfigEntryAuthFailed(
            "Authentication failed. Please update your credentials."
        ) from err
    except WFException as err:
        _LOGGER.error("Failed to connect to WaterFurnace service: %s", err)
        raise ConfigEntryNotReady(
            f"Failed to connect to WaterFurnace service: {err}"
        ) from err
    except Exception as err:
        _LOGGER.exception("Unexpected error during WaterFurnace setup")
        raise ConfigEntryNotReady(f"Unexpected error during setup: {err}") from err

    # Get device GWID for device registry
    gwid = client.gwid
    if not gwid:
        raise ConfigEntryNotReady("Device GWID not available")

    # Create the data update coordinator
    coordinator = WaterFurnaceDataUpdateCoordinator(hass, client, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = WaterFurnaceData(client=client, gwid=gwid)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, gwid)},
        manufacturer="WaterFurnace",
        name=f"WaterFurnace {gwid}",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove coordinator from hass.data
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
