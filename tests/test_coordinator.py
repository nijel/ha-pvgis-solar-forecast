"""Tests for the PVGIS Solar Forecast coordinator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.pvgis_solar_forecast.coordinator import (
    HISTORICAL_DAYS,
    ForecastSnapshot,
    PVGISSolarForecastCoordinator,
    SolarArrayForecast,
)
from custom_components.pvgis_solar_forecast.pvgis import PVGISData


class TestCloudFactor:
    """Test cloud factor calculation."""

    def test_no_cloud_data(self) -> None:
        """Test that no cloud data returns clear sky factor."""
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(
            datetime(2024, 7, 1, 12, 0, tzinfo=UTC), {}
        )
        assert factor == 1.0

    def test_clear_sky(self) -> None:
        """Test 0% cloud coverage."""
        now = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)
        coverage = {now.isoformat(): 0.0}
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(now, coverage)
        assert factor == 1.0

    def test_fully_overcast(self) -> None:
        """Test 100% cloud coverage."""
        now = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)
        coverage = {now.isoformat(): 100.0}
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(now, coverage)
        assert factor == pytest.approx(0.2)

    def test_partial_clouds(self) -> None:
        """Test 50% cloud coverage."""
        now = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)
        coverage = {now.isoformat(): 50.0}
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(now, coverage)
        assert factor == pytest.approx(0.6)

    def test_closest_forecast_time(self) -> None:
        """Test that the closest forecast time is used."""
        dt = datetime(2024, 7, 1, 12, 30, tzinfo=UTC)
        coverage = {
            datetime(2024, 7, 1, 12, 0, tzinfo=UTC).isoformat(): 20.0,
            datetime(2024, 7, 1, 13, 0, tzinfo=UTC).isoformat(): 80.0,
        }
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(dt, coverage)
        # Should use 12:00 (20% clouds) as it's closer
        assert factor == pytest.approx(0.84)

    def test_too_far_forecast(self) -> None:
        """Test that forecasts more than 3 hours away are ignored."""
        dt = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)
        coverage = {
            datetime(2024, 7, 1, 18, 0, tzinfo=UTC).isoformat(): 100.0,
        }
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(dt, coverage)
        assert factor == 1.0

    def test_timezone_naive_forecast_string(self) -> None:
        """Test handling timezone-naive ISO strings (without timezone info)."""
        # Some weather providers return ISO strings without timezone
        dt = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)
        # Simulate a naive ISO string (no timezone suffix)
        naive_iso = "2024-07-01T12:00:00"
        coverage = {naive_iso: 50.0}
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(dt, coverage)
        assert factor == pytest.approx(0.6)

    def test_timezone_aware_forecast_string(self) -> None:
        """Test handling timezone-aware ISO strings (Aladin integration case)."""
        # Aladin integration provides timezone-aware ISO strings
        dt = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)
        # Simulate a timezone-aware ISO string (with +00:00 suffix)
        aware_iso = "2024-07-01T12:00:00+00:00"
        coverage = {aware_iso: 75.0}
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(dt, coverage)
        assert factor == pytest.approx(0.4)


class TestComputeForecast:
    """Test forecast computation."""

    def test_compute_forecast_clear_sky(self, mock_pvgis_data: PVGISData) -> None:
        """Test computing forecast with clear sky (no clouds)."""
        # Use a January date to match our test data
        now = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)

        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )
        forecast = coordinator.compute_forecast(mock_pvgis_data, {}, now)

        assert isinstance(forecast, SolarArrayForecast)
        assert forecast.power_production_now > 0
        # 7 days * 24 hours = 168 hours
        assert len(forecast.wh_hours) == 168
        # Should have energy data for multiple days
        assert len(forecast.energy_production_days) > 0

    def test_compute_forecast_with_clouds(self, mock_pvgis_data: PVGISData) -> None:
        """Test that clouds reduce production."""
        now = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)

        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )

        # Clear sky forecast
        clear_forecast = coordinator.compute_forecast(mock_pvgis_data, {}, now)

        # Overcast forecast
        cloud_coverage = {}
        for h in range(48):
            dt = now + timedelta(hours=h)
            cloud_coverage[dt.isoformat()] = 100.0

        cloudy_forecast = coordinator.compute_forecast(
            mock_pvgis_data, cloud_coverage, now
        )

        # Cloudy should produce less
        assert (
            cloudy_forecast.energy_production_today
            < clear_forecast.energy_production_today
        )

    def test_compute_total_forecast(self) -> None:
        """Test computing total forecast from wh_hours."""
        now = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
        today = now.date()

        wh_hours = {}
        for d in range(7):
            day = today + timedelta(days=d)
            for h in range(24):
                dt = datetime(day.year, day.month, day.day, h, tzinfo=UTC)
                wh_hours[dt.isoformat()] = 100.0 if 6 <= h <= 18 else 0.0

        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )
        forecast = coordinator.compute_total_forecast(wh_hours, now)

        assert forecast.energy_production_today == 1300.0  # 13 hours * 100
        assert forecast.energy_production_tomorrow == 1300.0  # 13 hours * 100
        # Should have 7 days of energy data
        assert len(forecast.energy_production_days) == 7
        for d in range(7):
            assert forecast.energy_production_days[d] == 1300.0


class TestHistoricalSnapshots:
    """Test historical forecast snapshot functionality."""

    def test_cleanup_historical_snapshots(self) -> None:
        """Test cleanup of old historical snapshots."""
        now = datetime(2024, 7, 15, 12, 0, tzinfo=UTC)

        # Create snapshots spanning 10 days
        snapshots = []
        for days_ago in range(10, 0, -1):
            snapshot_time = now - timedelta(days=days_ago)
            snapshots.append(
                ForecastSnapshot(
                    timestamp=snapshot_time,
                    wh_hours={
                        (snapshot_time + timedelta(hours=i)).isoformat(): 1000.0
                        for i in range(24)
                    },
                )
            )

        # Clean up snapshots
        cleaned = PVGISSolarForecastCoordinator._cleanup_historical_snapshots(
            snapshots, now
        )

        # Should keep only snapshots from the last HISTORICAL_DAYS
        assert len(cleaned) == HISTORICAL_DAYS

        # All remaining snapshots should be within the retention period
        cutoff = now - timedelta(days=HISTORICAL_DAYS)
        for snapshot in cleaned:
            assert snapshot.timestamp >= cutoff

    def test_cleanup_keeps_all_recent_snapshots(self) -> None:
        """Test that recent snapshots are all kept."""
        now = datetime(2024, 7, 15, 12, 0, tzinfo=UTC)

        # Create snapshots within the retention period
        snapshots = []
        for hours_ago in range(0, 48, 6):  # Every 6 hours for 2 days
            snapshot_time = now - timedelta(hours=hours_ago)
            snapshots.append(
                ForecastSnapshot(
                    timestamp=snapshot_time,
                    wh_hours={
                        (snapshot_time + timedelta(hours=i)).isoformat(): 1000.0
                        for i in range(24)
                    },
                )
            )

        original_count = len(snapshots)

        # Clean up snapshots
        cleaned = PVGISSolarForecastCoordinator._cleanup_historical_snapshots(
            snapshots, now
        )

        # Should keep all snapshots since they're all recent
        assert len(cleaned) == original_count


class TestSecondaryWeatherEntity:
    """Test secondary weather entity functionality."""

    def test_cloud_factor_with_limited_primary_forecast(self) -> None:
        """Test that cloud factor handles limited primary forecast correctly."""
        # Simulate a primary forecast with only 48 hours
        now = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)

        # Primary forecast: 48 hours
        primary_coverage = {}
        for h in range(48):
            dt = now + timedelta(hours=h)
            primary_coverage[dt.isoformat()] = 30.0

        # For hour 0, should use primary forecast
        factor_h0 = PVGISSolarForecastCoordinator.get_cloud_factor(
            now, primary_coverage
        )
        assert factor_h0 == pytest.approx(0.76)  # 30% clouds

        # For hour 60 (beyond 48h), should fall back to clear sky
        dt_h60 = now + timedelta(hours=60)
        factor_h60 = PVGISSolarForecastCoordinator.get_cloud_factor(
            dt_h60, primary_coverage
        )
        assert factor_h60 == 1.0  # Clear sky fallback

    def test_merged_cloud_coverage(self) -> None:
        """Test merging primary and secondary cloud coverage."""
        now = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)

        # Primary forecast: 48 hours with 30% clouds
        primary_coverage = {}
        for h in range(48):
            dt = now + timedelta(hours=h)
            primary_coverage[dt.isoformat()] = 30.0

        # Secondary forecast: 168 hours (7 days) with 50% clouds
        secondary_coverage = {}
        for h in range(168):
            dt = now + timedelta(hours=h)
            secondary_coverage[dt.isoformat()] = 50.0

        # Merge the forecasts (simulate what coordinator does)
        merged_coverage = primary_coverage.copy()
        for ts, coverage in secondary_coverage.items():
            if ts not in merged_coverage:
                merged_coverage[ts] = coverage

        # Should have 168 hours total (full 7 days)
        assert len(merged_coverage) == 168

        # First 48 hours should use primary (30%)
        for h in range(48):
            dt = now + timedelta(hours=h)
            factor = PVGISSolarForecastCoordinator.get_cloud_factor(dt, merged_coverage)
            assert factor == pytest.approx(0.76)  # 30% clouds from primary

        # Hours 48-168 should use secondary (50%)
        for h in range(48, 168):
            dt = now + timedelta(hours=h)
            factor = PVGISSolarForecastCoordinator.get_cloud_factor(dt, merged_coverage)
            assert factor == pytest.approx(0.6)  # 50% clouds from secondary


class TestTodayForecastEveningInstall:
    """Test that today's forecast includes all hours even when installed in evening."""

    def test_today_forecast_includes_all_hours(self) -> None:
        """Test that energy_production_today includes past hours of today.
        
        This validates the fix for the issue where installing in the evening
        showed zero for today's forecast because it only counted future hours.
        """
        # Simulate installing at 8 PM (20:00)
        now = datetime(2024, 1, 1, 20, 0, tzinfo=UTC)
        today = now.date()
        
        # Create wh_hours with production throughout the day (6 AM to 6 PM)
        # Even though it's 8 PM, the forecast should include all hours from 00:00
        wh_hours = {}
        for h in range(24):
            dt = datetime(today.year, today.month, today.day, h, tzinfo=UTC)
            # Production from 6 AM to 6 PM (13 hours)
            wh_hours[dt.isoformat()] = 100.0 if 6 <= h <= 18 else 0.0
        
        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )
        forecast = coordinator.compute_total_forecast(wh_hours, now)
        
        # energy_production_today should include ALL hours (including past hours)
        assert forecast.energy_production_today == 1300.0  # 13 hours * 100
        
        # energy_production_today_remaining should only include future hours
        # At 8 PM, all production hours (6 AM-6 PM) have passed, so remaining = 0
        assert forecast.energy_production_today_remaining == 0.0
    
    def test_today_forecast_with_compute_forecast(self, mock_pvgis_data: PVGISData) -> None:
        """Test compute_forecast includes all hours from midnight when called in evening."""
        # Simulate calling compute_forecast at 8 PM (20:00)
        now = datetime(2024, 1, 1, 20, 0, tzinfo=UTC)
        
        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )
        
        # Compute forecast with clear sky
        forecast = coordinator.compute_forecast(mock_pvgis_data, {}, now)
        
        # Should have 168 hours in forecast (7 days * 24 hours)
        assert len(forecast.wh_hours) == 168
        
        # The wh_hours should start from midnight (00:00), not from current hour (20:00)
        sorted_hours = sorted(forecast.wh_hours.keys())
        first_hour_dt = datetime.fromisoformat(sorted_hours[0])
        assert first_hour_dt.hour == 0  # Should start from midnight
        assert first_hour_dt.date() == now.date()  # Should be today
        
        # energy_production_today should include all hours from midnight to 23:59
        # even though it's 8 PM and some hours have passed
        assert forecast.energy_production_today > 0
        
        # energy_production_today_remaining should be less than or equal to today_total
        assert forecast.energy_production_today_remaining <= forecast.energy_production_today
