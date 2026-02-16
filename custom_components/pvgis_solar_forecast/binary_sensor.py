"""Binary sensor platform for PVGIS Solar Forecast."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
)
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
        self._attr_name = "Weather entity available"
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
