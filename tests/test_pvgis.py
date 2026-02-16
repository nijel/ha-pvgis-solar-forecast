"""Tests for the PVGIS API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.pvgis_solar_forecast.pvgis import (
    PVGISApiError,
    PVGISConnectionError,
    PVGISData,
    _parse_pvgis_response,
    fetch_pvgis_data,
)


class TestParsePvgisResponse:
    """Test PVGIS response parsing."""

    def test_parse_valid_response(self, mock_pvgis_response: dict) -> None:
        """Test parsing a valid PVGIS response."""
        data = _parse_pvgis_response(mock_pvgis_response)

        assert isinstance(data, PVGISData)
        # January 1st at noon
        assert data.get_power(1, 1, 12) == 1300.0
        # July 1st at noon
        assert data.get_power(7, 1, 12) == 2000.0
        # No data for midnight Jan 1
        assert data.get_power(1, 1, 0) == 0.0
        # No data at all for Feb 15
        assert data.get_power(2, 15, 12) == 0.0

    def test_parse_empty_hourly(self) -> None:
        """Test parsing response with empty hourly data."""
        data = _parse_pvgis_response({"outputs": {"hourly": []}})
        assert isinstance(data, PVGISData)
        assert data.get_power(1, 1, 12) == 0.0

    def test_parse_missing_outputs(self) -> None:
        """Test parsing response with missing outputs key."""
        with pytest.raises(PVGISApiError, match="Unexpected PVGIS response format"):
            _parse_pvgis_response({})

    def test_parse_missing_hourly(self) -> None:
        """Test parsing response with missing hourly key."""
        with pytest.raises(PVGISApiError, match="Unexpected PVGIS response format"):
            _parse_pvgis_response({"outputs": {}})

    def test_parse_malformed_item(self) -> None:
        """Test parsing response with malformed items."""
        data = _parse_pvgis_response(
            {
                "outputs": {
                    "hourly": [
                        {"time": "20160101:1200", "P": 1000.0},
                        {"time": "invalid", "P": 500.0},
                        {"time": "20160101:1300"},
                        {"P": 500.0},
                    ]
                }
            }
        )
        assert data.get_power(1, 1, 12) == 1000.0
        assert data.get_power(1, 1, 13) == 0.0

    def test_parse_averaging_multiple_years(self) -> None:
        """Test that data from multiple years is averaged."""
        data = _parse_pvgis_response(
            {
                "outputs": {
                    "hourly": [
                        {"time": "20160101:1200", "P": 1000.0},
                        {"time": "20170101:1200", "P": 500.0},
                    ]
                }
            }
        )
        # Should average: (1000 + 500) / 2 = 750
        assert data.get_power(1, 1, 12) == 750.0


class TestFetchPvgisData:
    """Test PVGIS API fetching."""

    @pytest.mark.asyncio
    async def test_fetch_success(self, mock_pvgis_response: dict) -> None:
        """Test successful API fetch."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_pvgis_response)

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=mock_context)

        result = await fetch_pvgis_data(
            session=mock_session,
            latitude=45.0,
            longitude=8.0,
            peakpower=5.0,
            loss=14.0,
            angle=35,
            aspect=0,
        )

        assert isinstance(result, PVGISData)
        assert result.get_power(1, 1, 12) == 1300.0

    @pytest.mark.asyncio
    async def test_fetch_api_error(self) -> None:
        """Test API error handling."""
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad request")

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=mock_context)

        with pytest.raises(PVGISApiError, match="status 400"):
            await fetch_pvgis_data(
                session=mock_session,
                latitude=45.0,
                longitude=8.0,
                peakpower=5.0,
                loss=14.0,
                angle=35,
                aspect=0,
            )

    @pytest.mark.asyncio
    async def test_fetch_connection_error(self) -> None:
        """Test connection error handling."""
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(
            side_effect=aiohttp.ClientError("Connection failed")
        )
        mock_context.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=mock_context)

        with pytest.raises(PVGISConnectionError, match="Failed to connect"):
            await fetch_pvgis_data(
                session=mock_session,
                latitude=45.0,
                longitude=8.0,
                peakpower=5.0,
                loss=14.0,
                angle=35,
                aspect=0,
            )
