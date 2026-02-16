"""Binary sensor platform for PVGIS Solar Forecast."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    PVGISSolarForecastConfigEntry,
    PVGISSolarForecastCoordinator,
    SolarForecastData,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PVGISSolarForecastConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PVGIS Solar Forecast binary sensors."""
    coordinator = entry.runtime_data

    entities: list[BinarySensorEntity] = [
        WeatherEntityAvailableBinarySensor(
            entry_id=entry.entry_id,
            coordinator=coordinator,
        )
    ]

    # Add per-array snow covered binary sensors
    if coordinator.data and coordinator.data.arrays:
        entities.extend(
            SnowCoveredBinarySensor(
                entry_id=entry.entry_id,
                coordinator=coordinator,
                array_name=array_name,
            )
            for array_name in coordinator.data.arrays
        )

    async_add_entities(entities)


class WeatherEntityAvailableBinarySensor(
    CoordinatorEntity[PVGISSolarForecastCoordinator], BinarySensorEntity
):
    """Binary sensor for weather entity availability."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: PVGISSolarForecastCoordinator,
    ) -> None:
        """Initialize weather entity available binary sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{entry_id}_weather_entity_available"
        self._attr_translation_key = "weather_entity_available"
        self._attr_icon = "mdi:weather-partly-cloudy"

        device_id = entry_id
        device_name = "Solar production forecast"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, device_id)},
            manufacturer="PVGIS",
            model="Solar Forecast",
            name=device_name,
            configuration_url="https://re.jrc.ec.europa.eu/pvg_tools/en/",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the weather entity is available."""
        data: SolarForecastData | None = self.coordinator.data
        if data is None:
            return None

        return data.weather_entity_available


class SnowCoveredBinarySensor(
    CoordinatorEntity[PVGISSolarForecastCoordinator], BinarySensorEntity
):
    """Binary sensor for snow coverage on a solar array."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: PVGISSolarForecastCoordinator,
        array_name: str,
    ) -> None:
        """Initialize snow covered binary sensor."""
        super().__init__(coordinator=coordinator)
        self._array_name = array_name
        self._attr_unique_id = f"{entry_id}_snow_covered_{array_name}"
        self._attr_translation_key = "snow_covered"
        self._attr_icon = "mdi:snowflake"

        device_id = f"{entry_id}_{array_name}"
        device_name = f"Solar forecast - {array_name}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, device_id)},
            manufacturer="PVGIS",
            model="Solar Forecast",
            name=device_name,
            configuration_url="https://re.jrc.ec.europa.eu/pvg_tools/en/",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the array is covered with snow."""
        data: SolarForecastData | None = self.coordinator.data
        if data is None:
            return None

        array_forecast = data.arrays.get(self._array_name)
        if array_forecast is None:
            return None

        return array_forecast.snow_covered
