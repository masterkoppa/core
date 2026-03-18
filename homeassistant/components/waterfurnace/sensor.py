"""Support for Waterfurnace."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from waterfurnace.waterfurnace import WFReading

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, WaterFurnaceConfigEntry
from .coordinator import WaterFurnaceCoordinator


@dataclass(frozen=True, kw_only=True)
class WaterFurnaceSensorEntityDescription(SensorEntityDescription):
    """Describes a WaterFurnace sensor entity."""

    value_fn: Callable[[WFReading], StateType]


SENSORS = [
    WaterFurnaceSensorEntityDescription(
        key="mode",
        translation_key="mode",
        value_fn=lambda data: data.mode,
    ),
    WaterFurnaceSensorEntityDescription(
        key="totalunitpower",
        translation_key="total_unit_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.totalunitpower,
    ),
    WaterFurnaceSensorEntityDescription(
        key="tstatactivesetpoint",
        translation_key="tstat_active_setpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.tstatactivesetpoint,
    ),
    WaterFurnaceSensorEntityDescription(
        key="leavingairtemp",
        translation_key="leaving_air_temp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.leavingairtemp,
    ),
    WaterFurnaceSensorEntityDescription(
        key="tstatroomtemp",
        translation_key="room_temp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.tstatroomtemp,
    ),
    WaterFurnaceSensorEntityDescription(
        key="enteringwatertemp",
        translation_key="entering_water_temp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.enteringwatertemp,
    ),
    WaterFurnaceSensorEntityDescription(
        key="tstathumidsetpoint",
        translation_key="tstat_humid_setpoint",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.tstathumidsetpoint,
    ),
    WaterFurnaceSensorEntityDescription(
        key="tstatrelativehumidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.tstatrelativehumidity,
    ),
    WaterFurnaceSensorEntityDescription(
        key="compressorpower",
        translation_key="compressor_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.compressorpower,
    ),
    WaterFurnaceSensorEntityDescription(
        key="fanpower",
        translation_key="fan_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.fanpower,
    ),
    WaterFurnaceSensorEntityDescription(
        key="auxpower",
        translation_key="aux_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.auxpower,
    ),
    WaterFurnaceSensorEntityDescription(
        key="looppumppower",
        translation_key="loop_pump_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.looppumppower,
    ),
    WaterFurnaceSensorEntityDescription(
        key="actualcompressorspeed",
        translation_key="actual_compressor_speed",
        value_fn=lambda data: data.actualcompressorspeed,
    ),
    WaterFurnaceSensorEntityDescription(
        key="airflowcurrentspeed",
        translation_key="airflow_current_speed",
        value_fn=lambda data: data.airflowcurrentspeed,
    ),
    WaterFurnaceSensorEntityDescription(
        key="tstatdehumidsetpoint",
        translation_key="tstat_dehumid_setpoint",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.tstatdehumidsetpoint,
    ),
    WaterFurnaceSensorEntityDescription(
        key="leavingwatertemp",
        translation_key="leaving_water_temp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.leavingwatertemp,
    ),
    WaterFurnaceSensorEntityDescription(
        key="tstatheatingsetpoint",
        translation_key="tstat_heating_setpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.tstatheatingsetpoint,
    ),
    WaterFurnaceSensorEntityDescription(
        key="tstatcoolingsetpoint",
        translation_key="tstat_cooling_setpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.tstatcoolingsetpoint,
    ),
    WaterFurnaceSensorEntityDescription(
        key="waterflowrate",
        translation_key="water_flow_rate",
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.waterflowrate,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WaterFurnaceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Waterfurnace sensors from a config entry."""
    async_add_entities(
        WaterFurnaceSensor(coordinator, description)
        for coordinator in config_entry.runtime_data.values()
        for description in SENSORS
    )


class WaterFurnaceSensor(CoordinatorEntity[WaterFurnaceCoordinator], SensorEntity):
    """Implementing the Waterfurnace sensor."""

    entity_description: WaterFurnaceSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WaterFurnaceCoordinator,
        description: WaterFurnaceSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = f"{coordinator.unit}_{description.key}"

        device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unit)},
            manufacturer="WaterFurnace",
            name="WaterFurnace System",
        )

        if coordinator.device_metadata:
            if coordinator.device_metadata.description:
                # Eg. Series 7
                device_info["model"] = coordinator.device_metadata.description
            if coordinator.device_metadata.awlabctypedesc:
                # Eg. Series 7, 5 Ton
                device_info["name"] = coordinator.device_metadata.awlabctypedesc

        self._attr_device_info = device_info

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
