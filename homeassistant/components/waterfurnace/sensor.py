"""Support for WaterFurnace sensors."""

from __future__ import annotations

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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WaterFurnaceDataUpdateCoordinator
from .models import WaterFurnaceConfigEntry

PARALLEL_UPDATES = 0

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="mode",
        translation_key="mode",
        icon="mdi:gauge",
    ),
    SensorEntityDescription(
        key="totalunitpower",
        translation_key="totalunitpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tstatactivesetpoint",
        translation_key="tstatactivesetpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="leavingairtemp",
        translation_key="leavingairtemp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tstatroomtemp",
        translation_key="tstatroomtemp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="enteringwatertemp",
        translation_key="enteringwatertemp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tstathumidsetpoint",
        translation_key="tstathumidsetpoint",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tstatrelativehumidity",
        translation_key="tstatrelativehumidity",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="compressorpower",
        translation_key="compressorpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="fanpower",
        translation_key="fanpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="auxpower",
        translation_key="auxpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="looppumppower",
        translation_key="looppumppower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="actualcompressorspeed",
        translation_key="actualcompressorspeed",
        icon="mdi:speedometer",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="airflowcurrentspeed",
        translation_key="airflowcurrentspeed",
        icon="mdi:fan",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="tstatdehumidsetpoint",
        translation_key="tstatdehumidsetpoint",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tstatheatingsetpoint",
        translation_key="tstatheatingsetpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="tstatcoolingsetpoint",
        translation_key="tstatcoolingsetpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="leavingwatertemp",
        translation_key="leavingwatertemp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="waterflowrate",
        translation_key="waterflowrate",
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        icon="mdi:waves-arrow-right",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WaterFurnaceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WaterFurnace sensor based on a config entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        WaterFurnaceSensor(coordinator, description, entry) for description in SENSORS
    )


class WaterFurnaceSensor(
    CoordinatorEntity[WaterFurnaceDataUpdateCoordinator], SensorEntity
):
    """Implementing the WaterFurnace sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WaterFurnaceDataUpdateCoordinator,
        description: SensorEntityDescription,
        entry: WaterFurnaceConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        # Set unique ID based on device GWID and sensor key
        self._attr_unique_id = f"{coordinator.gwid}_{description.key}"

        # Link to device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.gwid)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.entity_description.key in self.coordinator.data
            and self.coordinator.data.get(self.entity_description.key) is not None
        )

    @property
    def native_value(self) -> float | int | str | None:
        """Return the state of the sensor."""
        # Get the value from coordinator data using the sensor key
        return self.coordinator.data.get(self.entity_description.key)
