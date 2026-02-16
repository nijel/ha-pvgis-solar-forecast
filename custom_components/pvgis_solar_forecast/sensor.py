"""Sensor platform for PVGIS Solar Forecast."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    PVGISSolarForecastConfigEntry,
    PVGISSolarForecastCoordinator,
    SolarArrayForecast,
    SolarForecastData,
)


@dataclass(frozen=True)
class PVGISSolarForecastSensorEntityDescription(SensorEntityDescription):
    """Describes a PVGIS Solar Forecast Sensor."""

    state: Callable[[SolarArrayForecast], StateType | datetime] | None = None


SENSORS: tuple[PVGISSolarForecastSensorEntityDescription, ...] = (
    PVGISSolarForecastSensorEntityDescription(
        key="energy_production_today",
        translation_key="energy_production_today",
        state=lambda f: f.energy_production_today,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    PVGISSolarForecastSensorEntityDescription(
        key="energy_production_today_remaining",
        translation_key="energy_production_today_remaining",
        state=lambda f: f.energy_production_today_remaining,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    PVGISSolarForecastSensorEntityDescription(
        key="energy_production_tomorrow",
        translation_key="energy_production_tomorrow",
        state=lambda f: f.energy_production_tomorrow,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    PVGISSolarForecastSensorEntityDescription(
        key="power_highest_peak_time_today",
        translation_key="power_highest_peak_time_today",
        device_class=SensorDeviceClass.TIMESTAMP,
        state=lambda f: f.power_highest_peak_time_today,
    ),
    PVGISSolarForecastSensorEntityDescription(
        key="power_highest_peak_time_tomorrow",
        translation_key="power_highest_peak_time_tomorrow",
        device_class=SensorDeviceClass.TIMESTAMP,
        state=lambda f: f.power_highest_peak_time_tomorrow,
    ),
    PVGISSolarForecastSensorEntityDescription(
        key="power_production_now",
        translation_key="power_production_now",
        device_class=SensorDeviceClass.POWER,
        state=lambda f: f.power_production_now,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    PVGISSolarForecastSensorEntityDescription(
        key="energy_current_hour",
        translation_key="energy_current_hour",
        state=lambda f: f.energy_current_hour,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    PVGISSolarForecastSensorEntityDescription(
        key="energy_next_hour",
        translation_key="energy_next_hour",
        state=lambda f: f.energy_next_hour,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PVGISSolarForecastConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PVGIS Solar Forecast sensors."""
    coordinator = entry.runtime_data

    # Create sensors for the total forecast
    entities: list[PVGISSolarForecastSensorEntity] = [
        PVGISSolarForecastSensorEntity(
            entry_id=entry.entry_id,
            coordinator=coordinator,
            entity_description=description,
            array_name=None,
        )
        for description in SENSORS
    ]

    # Create sensors for each individual array
    if coordinator.data and coordinator.data.arrays:
        for array_name in coordinator.data.arrays:
            entities.extend(
                PVGISSolarForecastSensorEntity(
                    entry_id=entry.entry_id,
                    coordinator=coordinator,
                    entity_description=description,
                    array_name=array_name,
                )
                for description in SENSORS
            )

    async_add_entities(entities)


class PVGISSolarForecastSensorEntity(
    CoordinatorEntity[PVGISSolarForecastCoordinator], SensorEntity
):
    """Defines a PVGIS Solar Forecast sensor."""

    entity_description: PVGISSolarForecastSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: PVGISSolarForecastCoordinator,
        entity_description: PVGISSolarForecastSensorEntityDescription,
        array_name: str | None = None,
    ) -> None:
        """Initialize PVGIS Solar Forecast sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = entity_description
        self._array_name = array_name

        if array_name:
            self._attr_unique_id = f"{entry_id}_{array_name}_{entity_description.key}"
            device_name = f"Solar forecast - {array_name}"
            device_id = f"{entry_id}_{array_name}"
        else:
            self._attr_unique_id = f"{entry_id}_{entity_description.key}"
            device_name = "Solar production forecast"
            device_id = entry_id

        self.entity_id = f"{SENSOR_DOMAIN}.pvgis_{entity_description.key}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, device_id)},
            manufacturer="PVGIS",
            model="Solar Forecast",
            name=device_name,
            configuration_url="https://re.jrc.ec.europa.eu/pvg_tools/en/",
        )

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        forecast = self._get_forecast()
        if forecast is None:
            return None

        if self.entity_description.state is not None:
            return self.entity_description.state(forecast)

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes with hourly forecast data."""
        forecast = self._get_forecast()
        if forecast is None:
            return None

        return {"wh_hours": forecast.wh_hours}

    def _get_forecast(self) -> SolarArrayForecast | None:
        """Get the forecast data for this sensor's array."""
        data: SolarForecastData | None = self.coordinator.data
        if data is None:
            return None

        if self._array_name is not None:
            return data.arrays.get(self._array_name)

        return data.total
