"""Test WaterFurnace sensor platform."""

from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the WaterFurnace integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.waterfurnace.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_coordinator_updates(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that coordinator updates work correctly."""
    # Verify initial state
    state = hass.states.get("sensor.waterfurnace_test_gwid_12345_furnace_mode")
    assert state is not None
    initial_value = state.state

    # Update mock data to return different value
    device_data = {"mode": "cooling", "totalunitpower": 5000}
    mock_data = Mock()
    for key, value in device_data.items():
        setattr(mock_data, key, value)
    mock_waterfurnace_client.read.return_value = mock_data

    # Advance time to trigger coordinator update (10 second interval)
    freezer.tick(15)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify state updated
    state = hass.states.get("sensor.waterfurnace_test_gwid_12345_furnace_mode")
    assert state is not None
    updated_value = state.state
    assert updated_value == "cooling"
    assert updated_value != initial_value


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_availability(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that sensors handle missing data correctly by becoming unavailable."""
    # Verify initial state - sensors should be available
    state = hass.states.get("sensor.waterfurnace_test_gwid_12345_water_flow_rate")
    assert state is not None
    assert state.state == "12.5"

    # Update mock data with missing waterflowrate (simulating device not reporting it)
    device_data = {
        "mode": "heating",
        "totalunitpower": 1500,
        "tstatactivesetpoint": 72,
        # waterflowrate is intentionally missing
    }
    mock_data = Mock()
    for key, value in device_data.items():
        setattr(mock_data, key, value)
    mock_waterfurnace_client.read.return_value = mock_data

    # Advance time to trigger coordinator update
    freezer.tick(15)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify sensor is now unavailable
    state = hass.states.get("sensor.waterfurnace_test_gwid_12345_water_flow_rate")
    assert state is not None
    assert state.state == "unavailable"
