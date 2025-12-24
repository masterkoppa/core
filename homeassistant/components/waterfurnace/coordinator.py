"""DataUpdateCoordinator for WaterFurnace integration."""

from __future__ import annotations

import logging

from waterfurnace.waterfurnace import WaterFurnace, WFCredentialError, WFException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class WaterFurnaceDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Manage fetching WaterFurnace data using the WaterFurnace library."""

    config_entry: ConfigEntry
    gwid: str

    def __init__(
        self,
        hass: HomeAssistant,
        client: WaterFurnace,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client
        self.gwid: str = client.gwid
        self._unavailable_logged = False

    async def _async_update_data(self) -> dict:
        """Fetch data from WaterFurnace.

        The WaterFurnace library uses blocking websocket calls, so we run
        them in the executor thread pool. The websocket connection is
        persistent and will be closed by the server if not polled at least
        every 30 seconds, which is why we use a 10-second update interval.
        """
        try:
            # Run the blocking read() call in the executor
            data = await self._load_data()

            if self._unavailable_logged:
                _LOGGER.info("WaterFurnace device %s is back online", self.gwid)
                self._unavailable_logged = False

        except WFCredentialError as err:
            # Authentication failed - credentials need to be refreshed
            if not self._unavailable_logged:
                _LOGGER.error(
                    "Authentication failed for WaterFurnace device %s", self.gwid
                )
                self._unavailable_logged = True
            raise ConfigEntryAuthFailed(
                f"Authentication failed for WaterFurnace device {self.gwid}"
            ) from err

        except WFException as err:
            # WFException indicates a recoverable error (network, server, etc.)
            # Try to reconnect by logging in again
            if not self._unavailable_logged:
                _LOGGER.info(
                    "WaterFurnace device %s is unavailable, attempting to reconnect: %s",
                    self.gwid,
                    err,
                )
                self._unavailable_logged = True

            try:
                # Attempt to reconnect
                await self.hass.async_add_executor_job(self.client.login)
                # Try reading again after reconnection
                data = await self._load_data()

                if self._unavailable_logged:
                    _LOGGER.info("WaterFurnace device %s reconnected", self.gwid)
                    self._unavailable_logged = False

            except (WFCredentialError, WFException) as reconnect_err:
                # Reconnection failed
                raise UpdateFailed(
                    f"Failed to reconnect to WaterFurnace device {self.gwid}: {reconnect_err}"
                ) from reconnect_err

            else:
                return data

        except Exception as err:
            # Unexpected error
            if not self._unavailable_logged:
                _LOGGER.exception(
                    "Unexpected error fetching data for WaterFurnace device %s",
                    self.gwid,
                )
                self._unavailable_logged = True
            raise UpdateFailed(
                f"Unexpected error for WaterFurnace device {self.gwid}: {err}"
            ) from err

        else:
            return data

    async def _load_data(self) -> dict:
        """Fetch from WaterFurnace, and convert the data for sensor use.

        Consumers are expected to handle exceptions
        """
        # Run the blocking read() call in the executor
        data = await self.hass.async_add_executor_job(self.client.read)
        if not data:
            return {}

        # Convert the data object to a dictionary of attributes
        # The data object has attributes for each sensor value
        result = vars(data) if data else {}
        # mode has special handling to convert the value to a string
        result["mode"] = data.mode
        return result
