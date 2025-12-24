"""Models for the WaterFurnace integration."""

from __future__ import annotations

from dataclasses import dataclass

from waterfurnace.waterfurnace import WaterFurnace

from homeassistant.config_entries import ConfigEntry

from .coordinator import WaterFurnaceDataUpdateCoordinator


@dataclass
class WaterFurnaceData:
    """Data for the WaterFurnace integration."""

    client: WaterFurnace
    coordinator: WaterFurnaceDataUpdateCoordinator
    gwid: str


type WaterFurnaceConfigEntry = ConfigEntry[WaterFurnaceData]
