# PVGIS Solar Forecast for Home Assistant

[![🔌 Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=nijel&repository=ha-pvgis-solar-forecast&category=integration)

[![HACS Action](https://github.com/nijel/ha-pvgis-solar-forecast/actions/workflows/hacs.yml/badge.svg)](https://github.com/nijel/ha-pvgis-solar-forecast/actions/workflows/hacs.yml)
[![Validate with hassfest](https://github.com/nijel/ha-pvgis-solar-forecast/actions/workflows/hassfest.yml/badge.svg)](https://github.com/nijel/ha-pvgis-solar-forecast/actions/workflows/hassfest.yml)
[![Tests](https://github.com/nijel/ha-pvgis-solar-forecast/actions/workflows/test.yml/badge.svg)](https://github.com/nijel/ha-pvgis-solar-forecast/actions/workflows/test.yml)

A Home Assistant custom integration that provides solar production forecasts
using [PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/en/) (Photovoltaic
Geographical Information System) radiation data combined with weather forecasts.

## Features

- Uses PVGIS API to fetch historical solar radiation data (cached, refreshed monthly)
- Combines with user-selected weather forecast entity for cloud coverage adjustments
- Supports multiple solar arrays with individual configurations
- Provides per-array and total production forecasts
- Compatible with Home Assistant Energy Dashboard (drop-in replacement for Forecast.Solar)
- Sensors match existing solar forecast integrations for easy migration

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant instance
1. Click on "Integrations"
1. Click the three dots in the top right corner and select "Custom repositories"
1. Add `https://github.com/nijel/ha-pvgis-solar-forecast` as an Integration
1. Install the integration
1. Restart Home Assistant

### Manual

1. Copy `custom_components/pvgis_solar_forecast` to your `config/custom_components/` directory
1. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
1. Search for "PVGIS Solar Forecast"
1. Configure your location (defaults to your Home Assistant location)
1. Optionally select a weather forecast entity for cloud coverage data
   - **Primary weather entity**: Used for short to medium term cloud coverage forecast
   - **Secondary weather entity** (optional): Used for long-term forecast when the primary entity only provides 24-48 hours of data
1. Add one or more solar arrays with their specifications:
   - **Declination**: Panel tilt angle (0° horizontal, 90° vertical)
   - **Azimuth**: Panel orientation (0° = South, 90° = West, -90° = East)
   - **Peak Power**: Total watt peak power of the array
   - **System Losses**: Percentage of system losses (default: 14%)
   - **Mounting Type**: Free-standing or building-integrated
   - **PV Technology**: Crystal Silicon, CIS, CdTe, or Unknown

## Sensors

The integration creates the following sensors for each array and for the total:

| Sensor                            | Description                                     | Unit      |
| --------------------------------- | ----------------------------------------------- | --------- |
| Energy production today           | Estimated total energy production for today     | kWh       |
| Energy production remaining today | Estimated remaining energy production for today | kWh       |
| Energy production tomorrow        | Estimated total energy production for tomorrow  | kWh       |
| Power production now              | Current estimated power production              | W         |
| Energy current hour               | Estimated energy production this hour           | kWh       |
| Energy next hour                  | Estimated energy production next hour           | kWh       |
| Highest peak time today           | Time of highest power peak today                | timestamp |
| Highest peak time tomorrow        | Time of highest power peak tomorrow             | timestamp |
| Clear sky power now               | Theoretical power under ideal clear-sky         | W         |
| Clear sky energy today            | Theoretical energy under ideal clear-sky        | kWh       |

**Note**: Clear sky sensors represent theoretical maximum production under ideal
conditions (0% clouds). These values are calculated dynamically using PVGIS irradiance
data and a clear-sky model, accounting for seasonal variations in typical weather
(winter is cloudier than summer).

## Energy Dashboard

This integration provides solar forecast data compatible with the Home Assistant
Energy Dashboard. After setup, you can select it as a solar forecast source in
your energy configuration.

## How It Works

1. **PVGIS Data**: The integration fetches hourly PV production estimates from
   the PVGIS API based on your panel configuration and location. This data
   represents typical production averaged over multiple years (Typical
   Meteorological Year - TMY), which includes typical cloud coverage patterns.
   It is cached and refreshed monthly since the underlying data doesn't change.

1. **Clear Sky Estimates**: The integration provides clear-sky sensors that
   represent theoretical maximum production under ideal conditions (0% clouds).
   These are calculated by scaling PVGIS TMY power using the ratio of clear-sky
   irradiance to TMY irradiance: `P_clearsky = P_tmy × (G_clearsky / G_tmy)`.
   A boost factor is applied to account for PVGIS conservatism and real-world
   conditions. This accounts for seasonal variations - winter TMY data includes
   more cloud effects than summer TMY data.

1. **Weather Adjustment**: If a weather entity is configured, cloud coverage
   forecasts are used to adjust production estimates. The forecast is calculated
   by scaling TMY power based on forecasted irradiance relative to TMY irradiance:
   `P_forecast = P_tmy × (I_forecast / I_tmy)`, where forecasted irradiance is
   interpolated between clear-sky (0% clouds) and overcast (100% clouds = 20% of
   clear-sky). A boost factor is applied to better match real-world production.
   If both primary and secondary weather entities are configured, the primary
   forecast is used when available, and the secondary provides extended forecast
   data beyond the primary's horizon.

1. **Forecast Generation**: The integration combines PVGIS data with weather
   forecasts to produce hourly production estimates for up to 7 days. The actual
   forecast duration depends on the available weather data from your configured
   weather entities.
