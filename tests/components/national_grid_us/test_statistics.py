"""Tests for the National Grid US long-term statistics import."""

from datetime import UTC, date, datetime, timedelta
from functools import partial
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from py_nationalgrid.exceptions import NationalGridError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.recorder.common import async_wait_recording_done

from homeassistant.components.national_grid_us.statistics import (
    bucket_readings,
    build_statistics,
    statistic_id,
)
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    get_metadata,
    statistics_during_period,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MOCK_ACCOUNT_ID

ELECTRIC_KEY = f"{MOCK_ACCOUNT_ID}_SP001"
GAS_KEY = f"{MOCK_ACCOUNT_ID}_SP002"
START = datetime(2025, 1, 1, tzinfo=UTC)


async def _async_sums(hass: HomeAssistant, *stat_ids: str) -> dict[str, list[float]]:
    """Return the cumulative sums stored for each statistic ID."""
    await async_wait_recording_done(hass)
    stats = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        START,
        None,
        set(stat_ids),
        "hour",
        None,
        {"sum"},
    )
    return {
        stat_id: [row["sum"] for row in stats.get(stat_id, [])] for stat_id in stat_ids
    }


def test_bucket_readings_splits_direction_and_sums_hours() -> None:
    """Test 15-minute readings are summed per hour and split by direction."""
    readings = [
        {"date": "2025-01-15T10:00:00.000Z", "quantity": 1.0},
        {"date": "2025-01-15T10:15:00.000Z", "quantity": 0.5},
        {"date": "2025-01-15T11:00:00.000Z", "quantity": -2.0},
        {"date": "not-a-date", "quantity": 9.0},
        {"date": "2025-01-15T10:30:00", "quantity": 1.0},
    ]
    ten = datetime(2025, 1, 15, 10, tzinfo=UTC)
    eleven = datetime(2025, 1, 15, 11, tzinfo=UTC)

    assert bucket_readings(readings, is_return=False) == {ten: 2.5}
    assert bucket_readings(readings, is_return=True) == {eleven: 2.0}


def test_bucket_readings_across_the_fall_back_rollback() -> None:
    """Test each reading is placed by its own offset when the clocks go back.

    On the rollback day the API jumps from 01:00-04:00 to 01:15-05:00 and has no
    records for the repeated hour, so nothing is double counted.
    """
    readings = [
        {"date": "2026-11-01T00:45:00.000-04:00", "quantity": 0.1},
        {"date": "2026-11-01T01:00:00.000-04:00", "quantity": 0.2},
        {"date": "2026-11-01T01:15:00.000-05:00", "quantity": 0.3},
        {"date": "2026-11-01T01:30:00.000-05:00", "quantity": 0.4},
        {"date": "2026-11-01T01:45:00.000-05:00", "quantity": 0.5},
        {"date": "2026-11-01T02:00:00.000-05:00", "quantity": 0.6},
        {"date": "2026-11-01T09:15:00.000-05:00", "quantity": -0.7},
    ]

    buckets = bucket_readings(readings, is_return=False)

    assert buckets == {
        datetime(2026, 11, 1, 4, tzinfo=UTC): 0.1,
        datetime(2026, 11, 1, 5, tzinfo=UTC): 0.2,
        datetime(2026, 11, 1, 6, tzinfo=UTC): pytest.approx(1.2),
        datetime(2026, 11, 1, 7, tzinfo=UTC): 0.6,
    }
    assert bucket_readings(readings, is_return=True) == {
        datetime(2026, 11, 1, 14, tzinfo=UTC): 0.7
    }


def test_build_statistics_continues_the_sum() -> None:
    """Test cumulative sums start from the supplied value."""
    ten = datetime(2025, 1, 15, 10, tzinfo=UTC)
    eleven = datetime(2025, 1, 15, 11, tzinfo=UTC)

    rows = build_statistics({eleven: 2.0, ten: 1.0}, 10.0)

    assert [(r["start"], r["state"], r["sum"]) for r in rows] == [
        (ten, 1.0, 11.0),
        (eleven, 2.0, 13.0),
    ]


@pytest.mark.freeze_time("2025-01-15T13:00:00+00:00")
async def test_statistics_imported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
) -> None:
    """Test AMI readings are imported as cumulative hourly statistics."""
    mock_national_grid_api.get_ami_energy_usages.side_effect = None
    mock_national_grid_api.get_ami_energy_usages.return_value = [
        {"date": "2025-01-10T00:00:00.000Z", "quantity": 4.0},
    ]
    mock_national_grid_api.get_ami_energy_usages_15min.return_value = [
        {"date": "2025-01-15T10:00:00.000Z", "quantity": 1.0},
        {"date": "2025-01-15T10:15:00.000Z", "quantity": 0.5},
        {"date": "2025-01-15T11:00:00.000Z", "quantity": -2.0},
    ]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    usage_id = statistic_id(ELECTRIC_KEY)
    return_id = statistic_id(ELECTRIC_KEY, is_return=True)
    gas_id = statistic_id(GAS_KEY)
    gas_return_id = statistic_id(GAS_KEY, is_return=True)
    sums = await _async_sums(hass, usage_id, return_id, gas_id, gas_return_id)

    assert sums[usage_id] == [4.0, 5.5]
    assert sums[return_id] == [2.0]
    # Gas has no return direction, so only its consumption series exists.
    assert sums[gas_id] == [4.0, 5.5]
    assert sums[gas_return_id] == []


@pytest.mark.freeze_time("2025-01-15T13:00:00+00:00")
async def test_statistics_units(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
) -> None:
    """Test electric is kWh and gas is therms, both in the energy unit class."""
    mock_national_grid_api.get_ami_energy_usages.side_effect = None
    mock_national_grid_api.get_ami_energy_usages.return_value = [
        {"date": "2025-01-10T00:00:00.000Z", "quantity": 4.0},
    ]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    electric_id = statistic_id(ELECTRIC_KEY)
    gas_id = statistic_id(GAS_KEY)
    metadata = await get_instance(hass).async_add_executor_job(
        partial(get_metadata, hass, statistic_ids={electric_id, gas_id})
    )

    assert metadata[electric_id][1]["unit_of_measurement"] == "kWh"
    assert metadata[electric_id][1]["unit_class"] == "energy"
    assert metadata[gas_id][1]["unit_of_measurement"] == "thm"
    assert metadata[gas_id][1]["unit_class"] == "energy"


@pytest.mark.freeze_time("2025-01-15T13:00:00+00:00")
async def test_first_import_backfills_all_history(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
) -> None:
    """Test the first import asks for all history and later ones only a week."""
    mock_national_grid_api.get_ami_energy_usages.side_effect = None
    mock_national_grid_api.get_ami_energy_usages.return_value = [
        {"date": "2025-01-10T00:00:00.000Z", "quantity": 4.0},
    ]
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    # The latest-reading fetch also calls this endpoint, so look for the history
    # request of each meter rather than comparing every call.
    first = [
        call.kwargs["date_from"]
        for call in mock_national_grid_api.get_ami_energy_usages.call_args_list
    ]
    assert first.count(date(1970, 1, 1)) == 2

    mock_national_grid_api.get_ami_energy_usages.reset_mock()
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_wait_recording_done(hass)

    later = [
        call.kwargs["date_from"]
        for call in mock_national_grid_api.get_ami_energy_usages.call_args_list
    ]
    assert date(1970, 1, 1) not in later
    assert later.count(date(2025, 1, 8)) == 2


@pytest.mark.freeze_time("2025-01-15T13:00:00+00:00")
async def test_statistics_fetch_failure_is_not_fatal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
) -> None:
    """Test failed history fetches do not fail the refresh."""
    mock_national_grid_api.get_ami_energy_usages_15min.side_effect = NationalGridError()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.freeze_time("2025-01-15T13:00:00+00:00")
async def test_statistics_sum_continues_across_refreshes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
) -> None:
    """Test a later refresh continues the cumulative sum of earlier imports."""
    mock_national_grid_api.get_ami_energy_usages.side_effect = None
    mock_national_grid_api.get_ami_energy_usages.return_value = []
    mock_national_grid_api.get_ami_energy_usages_15min.return_value = [
        {"date": "2025-01-15T10:00:00.000Z", "quantity": 1.0},
    ]
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    mock_national_grid_api.get_ami_energy_usages_15min.return_value = [
        {"date": "2025-01-15T11:00:00.000Z", "quantity": 2.0},
    ]
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    usage_id = statistic_id(ELECTRIC_KEY)
    assert (await _async_sums(hass, usage_id))[usage_id] == [1.0, 3.0]


@pytest.mark.freeze_time("2025-01-15T13:00:00+00:00")
async def test_reimporting_the_same_window_is_idempotent(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
) -> None:
    """Test refreshing twice with the same readings does not double the sums."""
    mock_national_grid_api.get_ami_energy_usages.side_effect = None
    mock_national_grid_api.get_ami_energy_usages.return_value = []
    mock_national_grid_api.get_ami_energy_usages_15min.return_value = [
        {"date": "2025-01-15T10:00:00.000Z", "quantity": 1.0},
        {"date": "2025-01-15T11:00:00.000Z", "quantity": 2.0},
    ]
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    usage_id = statistic_id(ELECTRIC_KEY)
    assert (await _async_sums(hass, usage_id))[usage_id] == [1.0, 3.0]
