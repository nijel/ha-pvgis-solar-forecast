# PVGIS Solar Forecast for Home Assistant

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
2. Click on "Integrations"
3. Click the three dots in the top right corner and select "Custom repositories"
4. Add `https://github.com/nijel/ha-pvgis-solar-forecast` as an Integration
5. Install the integration
6. Restart Home Assistant

### Manual

1. Copy `custom_components/pvgis_solar_forecast` to your `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "PVGIS Solar Forecast"
3. Configure your location (defaults to your Home Assistant location)
4. Optionally select a weather forecast entity for cloud coverage data
5. Add one or more solar arrays with their specifications:
   - **Declination**: Panel tilt angle (0° horizontal, 90° vertical)
   - **Azimuth**: Panel orientation (0° = South, 90° = West, -90° = East)
   - **Peak Power**: Total watt peak power of the array
   - **System Losses**: Percentage of system losses (default: 14%)
   - **Mounting Type**: Free-standing or building-integrated
   - **PV Technology**: Crystal Silicon, CIS, CdTe, or Unknown

## Sensors

The integration creates the following sensors for each array and for the total:

| Sensor | Description | Unit |
|--------|-------------|------|
| Energy production today | Estimated total energy production for today | kWh |
| Energy production remaining today | Estimated remaining energy production for today | kWh |
| Energy production tomorrow | Estimated total energy production for tomorrow | kWh |
| Power production now | Current estimated power production | W |
| Energy current hour | Estimated energy production this hour | kWh |
| Energy next hour | Estimated energy production next hour | kWh |
| Highest peak time today | Time of highest power peak today | timestamp |
| Highest peak time tomorrow | Time of highest power peak tomorrow | timestamp |

## Energy Dashboard

This integration provides solar forecast data compatible with the Home Assistant
Energy Dashboard. After setup, you can select it as a solar forecast source in
your energy configuration.

## How It Works

1. **PVGIS Data**: The integration fetches hourly PV production estimates from
   the PVGIS API based on your panel configuration and location. This data
   represents clear-sky production averaged over multiple years. It is cached
   and refreshed monthly since the underlying data doesn't change.

2. **Weather Adjustment**: If a weather entity is configured, cloud coverage
   forecasts are used to adjust the clear-sky estimates. The adjustment uses a
   linear mapping where 0% clouds = 100% of clear-sky production and 100%
   clouds = 20% of clear-sky production.

3. **Forecast Generation**: The integration combines PVGIS data with weather
   forecasts to produce hourly production estimates for the next 48 hours.