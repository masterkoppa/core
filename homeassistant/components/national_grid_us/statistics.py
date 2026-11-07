"""Long-term statistics import for the National Grid US integration."""

from datetime import UTC, date, datetime, timedelta
from functools import partial
import logging
import re

from py_nationalgrid import NationalGridClient
from py_nationalgrid.exceptions import (
    CannotConnectError,
    NationalGridError,
    RetryExhaustedError,
)
from py_nationalgrid.models import AmiEnergyUsage, Meter

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_conversion import EnergyConverter

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_HISTORY_START = date(1970, 1, 1)
# Recent days are fetched at 15-minute resolution, older days as hourly records.
_RECENT_DAYS = 3
# Days re-imported on every refresh to pick up late or backfilled readings.
_INCREMENTAL_DAYS = 7


def statistic_id(meter_key: str, *, is_return: bool = False) -> str:
    """Return the external statistic ID for a meter's hourly usage."""
    suffix = "return_usage" if is_return else "usage"
    return f"{DOMAIN}:{meter_key}_{suffix}".lower()


def _parse_start(value: str) -> datetime | None:
    """Parse an API timestamp into a UTC datetime."""
    cleaned = re.sub(r"\.\d+", "", value)
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def bucket_readings(
    readings: list[AmiEnergyUsage], *, is_return: bool
) -> dict[datetime, float]:
    """Sum readings into top-of-hour buckets for one direction.

    Consumption keeps non-negative quantities; return keeps negative ones as
    positive values.
    """
    hourly: dict[datetime, float] = {}
    for reading in readings:
        parsed = _parse_start(str(reading.get("date", "")))
        if parsed is None:
            continue
        quantity = float(reading.get("quantity", 0))
        if is_return:
            if quantity >= 0:
                continue
            quantity = -quantity
        elif quantity < 0:
            continue
        hour = parsed.replace(minute=0, second=0, microsecond=0)
        hourly[hour] = hourly.get(hour, 0.0) + quantity
    return hourly


def build_statistics(
    hourly: dict[datetime, float], starting_sum: float
) -> list[StatisticData]:
    """Build cumulative statistics rows from hourly totals."""
    total = starting_sum
    rows: list[StatisticData] = []
    for hour in sorted(hourly):
        total += hourly[hour]
        rows.append(StatisticData(start=hour, state=hourly[hour], sum=total))
    return rows


async def _async_has_statistics(hass: HomeAssistant, stat_id: str) -> bool:
    """Return whether any statistics were already imported for a series."""
    last = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1, stat_id, False, set()
    )
    return bool(last.get(stat_id))


async def _async_sum_before(
    hass: HomeAssistant, stat_id: str, before: datetime
) -> float:
    """Return the cumulative sum of the last imported hour before a time."""
    stats = await get_instance(hass).async_add_executor_job(
        partial(
            statistics_during_period,
            hass,
            datetime.fromtimestamp(0, tz=UTC),
            before,
            {stat_id},
            "hour",
            None,
            {"sum"},
        )
    )
    rows = stats.get(stat_id)
    if not rows:
        return 0.0
    return rows[-1].get("sum") or 0.0


async def _async_fetch_readings(
    client: NationalGridClient,
    meter: Meter,
    premise_number: int | str,
    today: date,
    *,
    first_import: bool,
) -> list[AmiEnergyUsage]:
    """Fetch hourly history plus the recent 15-minute readings for a meter.

    The two ranges are disjoint because the API includes both date bounds and
    overlapping hourly and 15-minute records would be summed twice.
    """
    recent_start = today - timedelta(days=_RECENT_DAYS)
    bulk_end = recent_start - timedelta(days=1)
    bulk_start = (
        _HISTORY_START if first_import else today - timedelta(days=_INCREMENTAL_DAYS)
    )
    readings: list[AmiEnergyUsage] = []
    for fetch, date_from, date_to in (
        (client.get_ami_energy_usages, bulk_start, bulk_end),
        (client.get_ami_energy_usages_15min, recent_start, today),
    ):
        try:
            readings.extend(
                await fetch(
                    meter_number=meter["meterNumber"],
                    premise_number=premise_number,
                    service_point_number=meter["servicePointNumber"],
                    meter_point_number=meter["meterPointNumber"],
                    date_from=date_from,
                    date_to=date_to,
                    fuel_type=meter["fuelType"].upper(),
                )
            )
        except (
            CannotConnectError,
            RetryExhaustedError,
            NationalGridError,
            ValueError,
        ) as err:
            _LOGGER.debug(
                "Could not fetch AMI readings for meter %s: %s",
                meter["meterNumber"],
                err,
            )
    return readings


async def async_import_meter_statistics(
    hass: HomeAssistant,
    client: NationalGridClient,
    meter_key: str,
    meter: Meter,
    premise_number: int | str,
    today: date,
) -> None:
    """Import long-term usage statistics for one AMI meter.

    Every run re-imports the whole fetched window, continuing the cumulative
    sum from the last hour before it, so late or backfilled readings fill in
    without any state kept between refreshes.
    """
    is_gas = meter["fuelType"].upper() == "GAS"
    unit = UnitOfEnergy.THERM if is_gas else UnitOfEnergy.KILO_WATT_HOUR
    consumption_id = statistic_id(meter_key)

    first_import = not await _async_has_statistics(hass, consumption_id)
    readings = await _async_fetch_readings(
        client, meter, premise_number, today, first_import=first_import
    )
    if not readings:
        return

    fuel = "Gas" if is_gas else "Electric"
    directions = (False,) if is_gas else (False, True)
    for is_return in directions:
        hourly = bucket_readings(readings, is_return=is_return)
        if not hourly:
            continue
        stat_id = statistic_id(meter_key, is_return=is_return)
        starting_sum = await _async_sum_before(hass, stat_id, min(hourly))
        metadata = StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"{fuel} meter {meter_key} {'return' if is_return else 'usage'}",
            source=DOMAIN,
            statistic_id=stat_id,
            unit_class=EnergyConverter.UNIT_CLASS,
            unit_of_measurement=unit,
        )
        async_add_external_statistics(
            hass, metadata, build_statistics(hourly, starting_sum)
        )
