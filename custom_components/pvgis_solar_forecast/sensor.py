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
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfPower
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
    PVGISSolarForecastSensorEntityDescription(
        key="peak_power_today",
        translation_key="peak_power_today",
        state=lambda f: f.peak_power_today,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    PVGISSolarForecastSensorEntityDescription(
        key="peak_power_tomorrow",
        translation_key="peak_power_tomorrow",
        state=lambda f: f.peak_power_tomorrow,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
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
    entities: list[PVGISSolarForecastSensorEntity | PVGISDiagnosticSensor] = [
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

    # Add diagnostic sensors
    entities.append(
        PVGISDiagnosticSensor(
            entry_id=entry.entry_id,
            coordinator=coordinator,
            key="cloud_coverage",
            name="Cloud coverage",
            icon="mdi:weather-cloudy",
            unit="%",
        )
    )
    entities.append(
        PVGISDiagnosticSensor(
            entry_id=entry.entry_id,
            coordinator=coordinator,
            key="weather_entity_available",
            name="Weather entity available",
            icon="mdi:weather-partly-cloudy",
        )
    )
    entities.append(
        PVGISDiagnosticSensor(
            entry_id=entry.entry_id,
            coordinator=coordinator,
            key="clear_sky_power_now",
            name="Clear sky power now",
            icon="mdi:white-balance-sunny",
            unit="W",
        )
    )
    entities.append(
        PVGISDiagnosticSensor(
            entry_id=entry.entry_id,
            coordinator=coordinator,
            key="clear_sky_energy_today",
            name="Clear sky energy today",
            icon="mdi:solar-power-variant",
            unit="Wh",
        )
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

        return {
            "wh_hours": forecast.wh_hours,
            "detailedForecast": forecast.detailed_forecast,
        }

    def _get_forecast(self) -> SolarArrayForecast | None:
        """Get the forecast data for this sensor's array."""
        data: SolarForecastData | None = self.coordinator.data
        if data is None:
            return None

        if self._array_name is not None:
            return data.arrays.get(self._array_name)

        return data.total


class PVGISDiagnosticSensor(
    CoordinatorEntity[PVGISSolarForecastCoordinator], SensorEntity
):
    """Diagnostic sensor for PVGIS Solar Forecast."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: PVGISSolarForecastCoordinator,
        key: str,
        name: str,
        icon: str | None = None,
        unit: str | None = None,
    ) -> None:
        """Initialize diagnostic sensor."""
        super().__init__(coordinator=coordinator)
        self._key = key
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self.entity_id = f"{SENSOR_DOMAIN}.pvgis_{key}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="PVGIS",
            model="Solar Forecast",
            name="Solar production forecast",
            configuration_url="https://re.jrc.ec.europa.eu/pvg_tools/en/",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        data: SolarForecastData | None = self.coordinator.data
        if data is None:
            return None

        if self._key == "cloud_coverage":
            return data.cloud_coverage_used
        if self._key == "weather_entity_available":
            return data.weather_entity_available
        if self._key == "clear_sky_power_now":
            return data.clear_sky_power_now
        if self._key == "clear_sky_energy_today":
            return data.clear_sky_energy_today

        return None
